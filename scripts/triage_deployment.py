#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "requests",
# ]
# ///
"""Comprehensive deployment triage playbook with cached status, e2e tests, and code quality checks."""

import json
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import requests

# Constants
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TMP_DIR = PROJECT_ROOT / "tmp"
CACHE_DIR = TMP_DIR / "triage-cache"


# Colors for output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")


def get_file_mtime(file_path: Path) -> float:
    """Get file modification time, return 0 if file doesn't exist."""
    try:
        return file_path.stat().st_mtime
    except FileNotFoundError:
        return 0


def is_cache_fresh(cache_file: Path, source_files: list[Path], max_age_minutes: int = 5) -> bool:
    """Check if cache file is fresh compared to source files and max age."""
    if not cache_file.exists():
        return False

    cache_mtime = get_file_mtime(cache_file)

    # Check if cache is too old
    if time.time() - cache_mtime > max_age_minutes * 60:
        return False

    # Check if any source file is newer than cache
    for source_file in source_files:
        if get_file_mtime(source_file) > cache_mtime:
            return False

    return True


def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def get_stack_outputs_cached(stack_name: str, region: str) -> dict[str, Any]:
    """Get CloudFormation stack outputs with caching."""
    cache_file = CACHE_DIR / f"{stack_name}_{region}_outputs.json"

    if is_cache_fresh(cache_file, [], max_age_minutes=2):
        print_info(f"Using cached outputs for {stack_name}")
        return json.loads(cache_file.read_text())

    print_info(f"Fetching fresh outputs for {stack_name}")

    cmd = [
        "aws",
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        stack_name,
        "--region",
        region,
        "--query",
        "Stacks[0]",
        "--output",
        "json",
    ]

    exit_code, stdout, stderr = run_command(cmd)

    if exit_code != 0:
        print_error(f"Failed to get stack outputs: {stderr}")
        return {}

    try:
        stack_data = json.loads(stdout)

        # Parse outputs into key-value pairs
        outputs = {}
        for output in stack_data.get("Outputs", []):
            outputs[output["OutputKey"]] = output["OutputValue"]

        # Add stack metadata
        result = {
            "StackName": stack_data.get("StackName"),
            "StackStatus": stack_data.get("StackStatus"),
            "LastUpdatedTime": stack_data.get("LastUpdatedTime"),
            "CreationTime": stack_data.get("CreationTime"),
            "Outputs": outputs,
            "CacheTime": datetime.now().isoformat(),
        }

        # Cache the result
        cache_file.write_text(json.dumps(result, indent=2))

        return result

    except json.JSONDecodeError as e:
        print_error(f"Failed to parse stack outputs: {e}")
        return {}


def check_lambda_function_status(function_name: str, region: str) -> dict[str, Any]:
    """Check Lambda function status and code."""
    cache_file = CACHE_DIR / f"{function_name}_lambda_status.json"

    # Check if we have fresh cache
    source_files = [
        PROJECT_ROOT / "cdk" / "lambda-edge" / "auth_handler.py",
        PROJECT_ROOT / "cdk" / "lambda-edge" / "auth_handler.py.template",
    ]

    if is_cache_fresh(cache_file, source_files, max_age_minutes=5):
        print_info(f"Using cached Lambda status for {function_name}")
        return json.loads(cache_file.read_text())

    print_info(f"Checking Lambda function {function_name}")

    try:
        lambda_client = boto3.client("lambda", region_name=region)

        # Get function configuration
        response = lambda_client.get_function(FunctionName=function_name)
        config = response["Configuration"]
        code_info = response["Code"]

        # Download and check code
        code_location = code_info["Location"]
        handler_file = download_lambda_code(code_location)
        code_check = analyze_lambda_code_content(handler_file) if handler_file else {"error": "Failed to download code"}

        # Get all versions of the function
        versions = get_lambda_versions(function_name, lambda_client)

        result = {
            "FunctionName": config["FunctionName"],
            "FunctionArn": config["FunctionArn"],
            "Runtime": config["Runtime"],
            "LastModified": config["LastModified"],
            "Version": config["Version"],
            "CodeSha256": config["CodeSha256"],
            "CodeLocation": code_location,
            "CodeCheck": code_check,
            "Versions": versions,
            "CacheTime": datetime.now().isoformat(),
        }

        # Cache the result
        cache_file.write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print_error(f"Failed to check Lambda function: {e}")
        return {"error": str(e)}


def get_lambda_versions(function_name: str, lambda_client=None) -> list[dict[str, Any]]:
    """Get all versions of a Lambda function with their details."""
    if lambda_client is None:
        lambda_client = boto3.client("lambda", region_name="us-east-1")

    try:
        response = lambda_client.list_versions_by_function(FunctionName=function_name)

        versions = []
        for version_info in response["Versions"]:
            # Parse last modified time
            last_modified = version_info["LastModified"]
            if isinstance(last_modified, str):
                # Parse AWS timestamp format
                modified_time = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
            else:
                modified_time = last_modified

            if modified_time.tzinfo is not None:
                modified_time = modified_time.replace(tzinfo=None)

            # Calculate age
            age_minutes = (datetime.now() - modified_time).total_seconds() / 60

            version_data = {
                "Version": version_info["Version"],
                "LastModified": modified_time.isoformat(),
                "CodeSha256": version_info["CodeSha256"],
                "AgeMinutes": round(age_minutes, 1),
                "IsRecent": age_minutes < 60,  # Consider recent if less than 1 hour old
            }

            versions.append(version_data)

        # Sort by version number (handle $LATEST specially)
        versions.sort(key=lambda x: 999999 if x["Version"] == "$LATEST" else int(x["Version"]))

        return versions

    except Exception as e:
        print_error(f"Failed to get Lambda versions: {e}")
        return []


def download_lambda_code(code_location: str) -> Path | None:
    """Download and extract Lambda code to temp directory."""
    try:
        # Download the code
        response = requests.get(code_location, timeout=30)
        response.raise_for_status()

        # Save to temp file and extract
        code_zip_path = TMP_DIR / "lambda-code-check.zip"
        code_extract_path = TMP_DIR / "lambda-code-check"

        code_zip_path.write_bytes(response.content)

        # Extract code
        with zipfile.ZipFile(code_zip_path, "r") as zip_file:
            zip_file.extractall(code_extract_path)

        # Return path to extracted auth_handler.py
        handler_file = code_extract_path / "auth_handler.py"
        return handler_file if handler_file.exists() else None

    except Exception as e:
        print_error(f"Failed to download Lambda code: {e}")
        return None


def analyze_lambda_code_content(handler_file: Path) -> dict[str, Any]:
    """Analyze Lambda code content for key patterns."""
    try:
        if not handler_file.exists():
            return {"error": "auth_handler.py not found"}

        content = handler_file.read_text()

        # Check for key patterns
        has_login_endpoint = "/login?" in content
        has_oauth2_endpoint = "/oauth2/authorize?" in content
        has_templated_values = "{{" not in content  # Should be replaced

        # Extract key values
        cognito_domain = None
        client_id = None

        for line in content.split("\n"):
            if line.startswith("COGNITO_DOMAIN = "):
                cognito_domain = line.split('"')[1]
            elif line.startswith("COGNITO_CLIENT_ID = "):
                client_id = line.split('"')[1]

        return {
            "has_login_endpoint": has_login_endpoint,
            "has_oauth2_endpoint": has_oauth2_endpoint,
            "has_templated_values": has_templated_values,
            "cognito_domain": cognito_domain,
            "client_id": client_id,
            "code_size": len(content),
            "last_checked": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": f"Failed to analyze Lambda code: {e}"}


def check_cloudfront_distribution(distribution_id: str) -> dict[str, Any]:
    """Check CloudFront distribution status."""
    cache_file = CACHE_DIR / f"{distribution_id}_cloudfront_status.json"

    if is_cache_fresh(cache_file, [], max_age_minutes=2):
        print_info(f"Using cached CloudFront status for {distribution_id}")
        return json.loads(cache_file.read_text())

    print_info(f"Checking CloudFront distribution {distribution_id}")

    try:
        cf_client = boto3.client("cloudfront")

        # Get distribution config
        response = cf_client.get_distribution(Id=distribution_id)
        config = response["Distribution"]["DistributionConfig"]

        # Get Lambda associations
        lambda_associations = []
        default_behavior = config.get("DefaultCacheBehavior", {})
        lambda_function_associations = default_behavior.get("LambdaFunctionAssociations", {})

        for item in lambda_function_associations.get("Items", []):
            lambda_associations.append(
                {
                    "LambdaFunctionARN": item["LambdaFunctionARN"],
                    "EventType": item["EventType"],
                    "IncludeBody": item.get("IncludeBody", False),
                }
            )

        # Get recent invalidations
        recent_invalidations = check_recent_invalidations(distribution_id, cf_client)

        result = {
            "DistributionId": distribution_id,
            "DomainName": config.get("DomainName", response["Distribution"]["DomainName"]),
            "Status": response["Distribution"]["Status"],
            "LastModifiedTime": response["Distribution"]["LastModifiedTime"].isoformat(),
            "LambdaAssociations": lambda_associations,
            "RecentInvalidations": recent_invalidations,
            "CacheTime": datetime.now().isoformat(),
        }

        # Cache the result
        cache_file.write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print_error(f"Failed to check CloudFront distribution: {e}")
        return {"error": str(e)}


def check_recent_invalidations(distribution_id: str, cf_client=None) -> list[dict[str, Any]]:
    """Check for recent CloudFront invalidations."""
    if cf_client is None:
        cf_client = boto3.client("cloudfront")

    try:
        # Get recent invalidations (increase limit and handle pagination)
        response = cf_client.list_invalidations(
            DistributionId=distribution_id,
            MaxItems="100",  # Increased to capture more invalidations
        )

        invalidations = []
        current_time = datetime.now()

        # Get all invalidation items and sort by creation time (newest first)
        items = response.get("InvalidationList", {}).get("Items", [])

        for item in items:
            # Parse datetime - handle AWS datetime format
            create_time_str = item["CreateTime"]
            if isinstance(create_time_str, str):
                create_time = datetime.fromisoformat(create_time_str.replace("Z", "+00:00"))
            else:
                # If it's already a datetime object from boto3
                create_time = create_time_str

            # Calculate age in minutes
            if create_time.tzinfo is not None:
                create_time = create_time.replace(tzinfo=None)
            age_minutes = (current_time - create_time).total_seconds() / 60

            invalidation_data = {
                "Id": item["Id"],
                "Status": item["Status"],
                "CreateTime": create_time.isoformat() if hasattr(create_time, "isoformat") else str(create_time),
                "AgeMinutes": round(age_minutes, 1),
                "IsRecent": age_minutes < 30,  # Consider recent if less than 30 minutes old
                "CreateTimeObj": create_time,  # Keep for sorting
            }

            # Get detailed info for recent invalidations
            if age_minutes < 60:  # Only get details for invalidations in last hour
                try:
                    detail_response = cf_client.get_invalidation(DistributionId=distribution_id, Id=item["Id"])
                    invalidation_detail = detail_response["Invalidation"]
                    invalidation_data.update(
                        {
                            "Paths": invalidation_detail["InvalidationBatch"]["Paths"]["Items"],
                            "CallerReference": invalidation_detail["InvalidationBatch"]["CallerReference"],
                        }
                    )
                except Exception as e:
                    invalidation_data["DetailError"] = str(e)

            invalidations.append(invalidation_data)

        # Sort by creation time (newest first)
        invalidations.sort(key=lambda x: x["CreateTimeObj"], reverse=True)

        # Remove the temporary CreateTimeObj field
        for inv in invalidations:
            inv.pop("CreateTimeObj", None)

        return invalidations

    except Exception as e:
        print_error(f"Failed to check invalidations: {e}")
        return []


def test_endpoint_response(url: str) -> dict[str, Any]:
    """Test an endpoint and analyze the response."""
    cache_file = CACHE_DIR / f"endpoint_test_{urlparse(url).netloc}_{urlparse(url).path.replace('/', '_')}.json"

    if is_cache_fresh(cache_file, [], max_age_minutes=1):
        print_info(f"Using cached endpoint test for {url}")
        return json.loads(cache_file.read_text())

    print_info(f"Testing endpoint {url}")

    try:
        response = requests.head(url, timeout=10, allow_redirects=False)

        result = {
            "url": url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "redirect_location": response.headers.get("Location"),
            "x_cache": response.headers.get("X-Cache"),
            "test_time": datetime.now().isoformat(),
        }

        # Analyze redirect location
        if result["redirect_location"]:
            parsed_redirect = urlparse(result["redirect_location"])
            result["redirect_analysis"] = {
                "domain": parsed_redirect.netloc,
                "path": parsed_redirect.path,
                "uses_login_endpoint": "/login" in parsed_redirect.path,
                "uses_oauth2_endpoint": "/oauth2/authorize" in parsed_redirect.path,
                "query_params": dict(param.split("=") for param in parsed_redirect.query.split("&") if "=" in param),
            }

        # Cache the result
        cache_file.write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print_error(f"Failed to test endpoint: {e}")
        return {"error": str(e)}


def extract_test_failure_summary(test_output: str) -> dict[str, Any]:
    """Extract test failure summary from pytest output."""
    import re

    failures = []
    errors = []

    # Split into lines for analysis
    lines = test_output.split("\n")

    # Look for FAILED test patterns
    failed_pattern = re.compile(r"FAILED\s+([^\s]+)\s*-\s*(.*)")
    error_pattern = re.compile(r"ERROR\s+([^\s]+)\s*-\s*(.*)")

    # Extract assertion errors and other failure details
    current_test = None

    for line in lines:
        line = line.strip()

        # Check for failed test
        failed_match = failed_pattern.search(line)
        if failed_match:
            test_name = failed_match.group(1)
            reason = failed_match.group(2) if failed_match.group(2) else "No reason provided"
            failures.append({"test": test_name, "reason": reason, "type": "FAILED"})
            continue

        # Check for error test
        error_match = error_pattern.search(line)
        if error_match:
            test_name = error_match.group(1)
            reason = error_match.group(2) if error_match.group(2) else "No reason provided"
            errors.append({"test": test_name, "reason": reason, "type": "ERROR"})
            continue

        # Look for assertion errors and other detailed failures
        if "AssertionError" in line:
            failures.append({"test": current_test or "Unknown test", "reason": line, "type": "AssertionError"})
        elif "TimeoutError" in line:
            failures.append({"test": current_test or "Unknown test", "reason": line, "type": "TimeoutError"})
        elif line.startswith("def test_") or "::test_" in line:
            current_test = line

    # Look for common failure patterns in short form
    short_failures = []

    # Browser/network related failures
    if "connection refused" in test_output.lower():
        short_failures.append("Connection refused - service may not be running")
    if "timeout" in test_output.lower():
        short_failures.append("Timeout error - service may be slow or unreachable")
    if "certificate" in test_output.lower() or "ssl" in test_output.lower():
        short_failures.append("SSL/Certificate error")
    if "unauthorized" in test_output.lower() or "401" in test_output:
        short_failures.append("Authentication/authorization error")
    if "not found" in test_output.lower() or "404" in test_output:
        short_failures.append("Resource not found (404)")
    if "cloudfront" in test_output.lower() and "error" in test_output.lower():
        short_failures.append("CloudFront distribution error")
    if "lambda" in test_output.lower() and "error" in test_output.lower():
        short_failures.append("Lambda function error")

    return {
        "failures": failures,
        "errors": errors,
        "short_failures": short_failures,
        "total_issues": len(failures) + len(errors),
        "has_failures": len(failures) > 0 or len(errors) > 0,
    }


def extract_lint_failure_summary(lint_output: str) -> dict[str, Any]:
    """Extract lint failure summary from ruff output."""
    import re

    issues = []

    # Split into lines for analysis
    lines = lint_output.split("\n")

    # Look for ruff error patterns: filename:line:column: code message
    ruff_pattern = re.compile(r"([^:]+):(\d+):(\d+):\s+([A-Z]\d+)\s+(.*)")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = ruff_pattern.search(line)
        if match:
            filename = match.group(1)
            line_num = match.group(2)
            col_num = match.group(3)
            code = match.group(4)
            message = match.group(5)

            issues.append(
                {"file": filename, "line": int(line_num), "column": int(col_num), "code": code, "message": message}
            )

    # Group by error type
    error_types = {}
    for issue in issues:
        code = issue["code"]
        if code not in error_types:
            error_types[code] = []
        error_types[code].append(issue)

    # Create summary of most common issues
    common_issues = []
    for code, issue_list in sorted(error_types.items(), key=lambda x: len(x[1]), reverse=True):
        if len(issue_list) > 0:
            common_issues.append(
                {
                    "code": code,
                    "count": len(issue_list),
                    "message": issue_list[0]["message"],
                    "files": list({issue["file"] for issue in issue_list}),
                }
            )

    return {
        "issues": issues,
        "total_issues": len(issues),
        "error_types": error_types,
        "common_issues": common_issues[:5],  # Top 5 most common
        "has_issues": len(issues) > 0,
    }


def run_e2e_tests() -> dict[str, Any]:
    """Run e2e tests and return results."""
    cache_file = CACHE_DIR / "e2e_test_results.json"

    # Check if cache is fresh (only cache for 1 minute since tests are deployment-dependent)
    if is_cache_fresh(cache_file, [], max_age_minutes=1):
        print_info("Using cached e2e test results")
        return json.loads(cache_file.read_text())

    print_info("Running e2e tests")

    # Run e2e tests
    exit_code, stdout, stderr = run_command(
        ["make", "test-e2e"],
        timeout=300,  # 5 minutes timeout for e2e tests
    )

    result = {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "passed": exit_code == 0,
        "test_time": datetime.now().isoformat(),
    }

    # Parse test results if possible
    if "passed" in stdout.lower() and "failed" in stdout.lower():
        # Try to extract test counts from pytest output
        import re

        test_match = re.search(r"(\d+) passed.*?(\d+) failed", stdout)
        if test_match:
            result["tests_passed"] = int(test_match.group(1))
            result["tests_failed"] = int(test_match.group(2))

    # Extract failure details
    result["failure_summary"] = extract_test_failure_summary(stdout + stderr)

    # Cache the result
    cache_file.write_text(json.dumps(result, indent=2))

    return result


def run_lint_checks() -> dict[str, Any]:
    """Run linting and formatting checks."""
    cache_file = CACHE_DIR / "lint_check_results.json"

    # Check source files for freshness
    source_files = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "cdk",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "frontend" / "src",
        PROJECT_ROOT / "pyproject.toml",
    ]

    # Filter to only existing files/directories
    existing_sources = [f for f in source_files if f.exists()]

    if is_cache_fresh(cache_file, existing_sources, max_age_minutes=5):
        print_info("Using cached lint check results")
        return json.loads(cache_file.read_text())

    print_info("Running lint and format checks")

    # Run lint command
    lint_exit_code, lint_stdout, lint_stderr = run_command(["make", "lint"], timeout=60)

    # Run format check (dry run) - use ruff directly since there's no format-check target
    format_exit_code, format_stdout, format_stderr = run_command(
        ["uv", "run", "ruff", "format", "--check", "."], timeout=60
    )

    result = {
        "lint": {
            "exit_code": lint_exit_code,
            "stdout": lint_stdout,
            "stderr": lint_stderr,
            "passed": lint_exit_code == 0,
            "failure_summary": (
                extract_lint_failure_summary(lint_stdout + lint_stderr) if lint_exit_code != 0 else None
            ),
        },
        "format": {
            "exit_code": format_exit_code,
            "stdout": format_stdout,
            "stderr": format_stderr,
            "passed": format_exit_code == 0,
            "failure_summary": extract_lint_failure_summary(format_stdout + format_stderr)
            if format_exit_code != 0
            else None,
        },
        "overall_passed": lint_exit_code == 0 and format_exit_code == 0,
        "check_time": datetime.now().isoformat(),
    }

    # Cache the result
    cache_file.write_text(json.dumps(result, indent=2))

    return result


def generate_combined_outputs() -> dict[str, Any]:
    """Generate combined outputs like make outputs but in JSON format."""
    cache_file = CACHE_DIR / "combined_outputs.json"

    # No source file dependencies for combined outputs - it's derived from stack outputs
    # which have their own caching logic
    if is_cache_fresh(cache_file, [], max_age_minutes=2):
        print_info("Using cached combined outputs")
        return json.loads(cache_file.read_text())

    print_info("Generating combined outputs")

    # Get both stack outputs (these have their own caching)
    auth_stack = get_stack_outputs_cached("SfltAuthStack", "ap-southeast-2")
    static_stack = get_stack_outputs_cached("SfltStaticSiteStack", "us-east-1")

    result = {
        "AuthStack": auth_stack,
        "StaticSiteStack": static_stack,
        "QuickAccess": {
            "CloudFrontURL": f"https://{static_stack.get('Outputs', {}).get('DistributionDomainName', 'unknown')}",
            "UserPoolId": auth_stack.get("Outputs", {}).get("UserPoolId"),
            "ClientId": auth_stack.get("Outputs", {}).get("UserPoolClientId"),
            "DistributionId": static_stack.get("Outputs", {}).get("DistributionId"),
        },
        "GeneratedTime": datetime.now().isoformat(),
    }

    # Cache the result
    cache_file.write_text(json.dumps(result, indent=2))

    return result


def analyze_deployment_status() -> dict[str, Any]:
    """Analyze overall deployment status."""
    print_header("Deployment Status Analysis")

    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Get combined outputs
    outputs = generate_combined_outputs()

    # Check key components
    distribution_id = outputs["QuickAccess"]["DistributionId"]
    lambda_arn = outputs["StaticSiteStack"]["Outputs"].get("AuthLambdaArn")

    if lambda_arn:
        lambda_name = lambda_arn.split(":")[-2]  # Extract function name from ARN
        lambda_status = check_lambda_function_status(lambda_name, "us-east-1")
    else:
        lambda_status = {"error": "Lambda ARN not found"}

    cloudfront_status = check_cloudfront_distribution(distribution_id)

    # Test endpoint
    cloudfront_url = outputs["QuickAccess"]["CloudFrontURL"]
    endpoint_test = test_endpoint_response(f"{cloudfront_url}/admin")

    # Analyze configuration drift
    config_analysis = analyze_configuration_drift()

    # Run e2e tests
    e2e_results = run_e2e_tests()

    # Run lint checks
    lint_results = run_lint_checks()

    result = {
        "timestamp": datetime.now().isoformat(),
        "outputs": outputs,
        "lambda_status": lambda_status,
        "cloudfront_status": cloudfront_status,
        "endpoint_test": endpoint_test,
        "config_analysis": config_analysis,
        "e2e_tests": e2e_results,
        "lint_checks": lint_results,
        "summary": generate_status_summary(
            outputs, lambda_status, cloudfront_status, endpoint_test, config_analysis, e2e_results, lint_results
        ),
    }

    # Save full analysis
    analysis_file = CACHE_DIR / "deployment_analysis.json"
    analysis_file.write_text(json.dumps(result, indent=2))

    return result


def analyze_configuration_drift() -> dict[str, Any]:
    """Check for configuration drift in generated files."""
    print_info("Analyzing configuration drift")

    # Check aws-exports.js
    aws_exports_file = PROJECT_ROOT / "frontend" / "src" / "aws-exports.js"
    auth_handler_file = PROJECT_ROOT / "cdk" / "lambda-edge" / "auth_handler.py"

    result = {
        "aws_exports": {
            "exists": aws_exports_file.exists(),
            "last_modified": get_file_mtime(aws_exports_file),
            "is_generated": False,
        },
        "auth_handler": {
            "exists": auth_handler_file.exists(),
            "last_modified": get_file_mtime(auth_handler_file),
            "is_generated": False,
        },
    }

    # Check if files contain generated markers
    if aws_exports_file.exists():
        content = aws_exports_file.read_text()
        result["aws_exports"]["is_generated"] = "Auto-generated by scripts/generate_aws_exports.py" in content

    if auth_handler_file.exists():
        content = auth_handler_file.read_text()
        result["auth_handler"]["is_generated"] = "injected by CDK at deployment time" in content

    return result


def generate_status_summary(
    outputs: dict,
    lambda_status: dict,
    cloudfront_status: dict,
    endpoint_test: dict,
    config_analysis: dict,
    e2e_results: dict,
    lint_results: dict,
) -> dict[str, Any]:
    """Generate a human-readable status summary."""
    issues = []
    warnings = []

    # Check Lambda code vs CloudFront association
    lambda_versions = lambda_status.get("Versions", [])
    cloudfront_lambda_arn = ""
    if cloudfront_status.get("LambdaAssociations"):
        cloudfront_lambda_arn = cloudfront_status["LambdaAssociations"][0].get("LambdaFunctionARN", "")

    # Extract version from CloudFront association ARN
    cloudfront_version = None
    if cloudfront_lambda_arn and ":" in cloudfront_lambda_arn:
        cloudfront_version = cloudfront_lambda_arn.split(":")[-1]

    # Check Lambda code (analyzing $LATEST)
    if lambda_status.get("CodeCheck", {}).get("has_login_endpoint"):
        print_success("Lambda $LATEST code uses /login endpoint")
    elif lambda_status.get("CodeCheck", {}).get("has_oauth2_endpoint"):
        issues.append("Lambda $LATEST code still uses /oauth2/authorize endpoint")

    # Check version mismatch - compare against most recent numbered version (not $LATEST)
    if cloudfront_version and lambda_versions:
        # Find the most recent numbered version (exclude $LATEST)
        numbered_versions = [v for v in lambda_versions if v.get("Version") != "$LATEST"]
        if numbered_versions:
            # Sort by version number (highest first)
            numbered_versions.sort(key=lambda x: int(x.get("Version", "0")), reverse=True)
            latest_numbered_version = numbered_versions[0]

            if cloudfront_version != latest_numbered_version.get("Version"):
                issues.append(
                    f"CloudFront uses Lambda version {cloudfront_version}, "
                    f"but latest numbered version is {latest_numbered_version.get('Version')}"
                )
                print_warning(
                    f"Version mismatch: CloudFront={cloudfront_version}, "
                    f"Latest numbered version={latest_numbered_version.get('Version')}"
                )
            else:
                print_success(f"CloudFront uses latest numbered Lambda version {cloudfront_version}")
        else:
            print_warning("No numbered Lambda versions found")

    # Check endpoint response
    if endpoint_test.get("redirect_analysis", {}).get("uses_login_endpoint"):
        print_success("Endpoint redirects to /login")
    elif endpoint_test.get("redirect_analysis", {}).get("uses_oauth2_endpoint"):
        issues.append("Endpoint still redirects to /oauth2/authorize (version mismatch?)")

    # Check cache headers
    x_cache = endpoint_test.get("x_cache", "")
    if "LambdaGeneratedResponse" in x_cache:
        print_success("Response generated by Lambda@Edge")
    else:
        warnings.append("Response may not be from Lambda@Edge")

    # Check recent invalidations
    recent_invalidations = cloudfront_status.get("RecentInvalidations", [])
    recent_completed = [inv for inv in recent_invalidations if inv.get("Status") == "Completed" and inv.get("IsRecent")]

    if recent_completed:
        print_success(f"Recent invalidation completed {recent_completed[0].get('AgeMinutes', 0):.1f} minutes ago")

    # Check configuration drift
    if not config_analysis["aws_exports"]["is_generated"]:
        warnings.append("aws-exports.js may not be generated from CDK outputs")

    if not config_analysis["auth_handler"]["is_generated"]:
        warnings.append("auth_handler.py may not be generated from template")

    # Check e2e tests
    if e2e_results.get("passed"):
        print_success("E2E tests passed")
    elif e2e_results.get("exit_code") == 0:
        print_success("E2E tests completed successfully")
    else:
        issues.append("E2E tests failed")
        if e2e_results.get("tests_failed", 0) > 0:
            issues.append(
                f"E2E tests: {e2e_results.get('tests_failed', 0)} failed, {e2e_results.get('tests_passed', 0)} passed"
            )

    # Check lint results
    if lint_results.get("overall_passed"):
        print_success("Lint and format checks passed")
    else:
        if not lint_results.get("lint", {}).get("passed"):
            issues.append("Linting checks failed")
        if not lint_results.get("format", {}).get("passed"):
            issues.append("Format checks failed")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "recommendations": generate_recommendations(issues, warnings, recent_invalidations, e2e_results, lint_results),
        "recent_invalidations": recent_invalidations,
        "e2e_status": e2e_results,
        "lint_status": lint_results,
    }


def generate_recommendations(
    issues: list[str],
    warnings: list[str],
    recent_invalidations: list[dict] = None,
    e2e_results: dict = None,
    lint_results: dict = None,
) -> list[str]:
    """Generate recommendations based on issues and warnings."""
    recommendations = []

    if recent_invalidations is None:
        recent_invalidations = []
    if e2e_results is None:
        e2e_results = {}
    if lint_results is None:
        lint_results = {}

    # Check if there are recent invalidations
    recent_completed = [inv for inv in recent_invalidations if inv.get("Status") == "Completed" and inv.get("IsRecent")]
    recent_in_progress = [inv for inv in recent_invalidations if inv.get("Status") == "InProgress"]

    for issue in issues:
        if "CloudFront uses Lambda version" in issue:
            recommendations.append("Version mismatch detected - redeploy CDK to update CloudFront association")
            recommendations.append("Run 'make deploy' to create new Lambda version and update CloudFront")
        elif "oauth2/authorize" in issue:
            if "Lambda code" in issue:
                recommendations.append("Run 'make generate-lambda-code' to update Lambda function code")
            elif "version mismatch" in issue:
                recommendations.append("Lambda version mismatch causing old code to execute")
            else:
                # Check invalidation status before recommending
                if recent_in_progress:
                    recommendations.append("CloudFront invalidation in progress - wait for completion")
                elif recent_completed:
                    age_minutes = recent_completed[0].get("AgeMinutes", 0)
                    if age_minutes < 15:
                        recommendations.append(
                            f"Recent invalidation completed {age_minutes:.1f} minutes ago - "
                            "cache may still be propagating"
                        )
                    else:
                        recommendations.append(
                            "Recent invalidation completed but cache still serving old content - "
                            "check Lambda@Edge association"
                        )
                else:
                    recommendations.append(
                        "Try: aws cloudfront create-invalidation --distribution-id <id> --paths '/*'"
                    )
        elif "E2E tests failed" in issue:
            recommendations.append("Run 'make test-e2e' to see detailed test failure output")

            # Add specific failure insights
            failure_summary = e2e_results.get("failure_summary", {})
            if failure_summary.get("short_failures"):
                recommendations.append("Common issues detected:")
                for short_failure in failure_summary["short_failures"][:3]:  # Top 3
                    recommendations.append(f"  - {short_failure}")

            if failure_summary.get("failures"):
                recommendations.append(f"Failed tests: {len(failure_summary['failures'])}")
                for failure in failure_summary["failures"][:2]:  # Show first 2
                    recommendations.append(
                        f"  - {failure.get('test', 'Unknown')}: {failure.get('reason', 'No reason')}"
                    )

        elif "Linting checks failed" in issue:
            recommendations.append("Run 'make lint' to see linting errors")

            # Add specific lint failure insights
            lint_summary = lint_results.get("lint", {}).get("failure_summary", {})
            if lint_summary and lint_summary.get("common_issues"):
                recommendations.append("Most common lint issues:")
                for common_issue in lint_summary["common_issues"][:3]:  # Top 3
                    recommendations.append(f"  - {common_issue['code']}: {common_issue['count']} occurrences")

            recommendations.append("Fix linting issues then run 'make format' to auto-format")

        elif "Format checks failed" in issue:
            recommendations.append("Run 'make format' to fix formatting issues")

            # Add specific format failure insights
            format_summary = lint_results.get("format", {}).get("failure_summary", {})
            if format_summary and format_summary.get("common_issues"):
                recommendations.append("Most common format issues:")
                for common_issue in format_summary["common_issues"][:3]:  # Top 3
                    recommendations.append(f"  - {common_issue['code']}: {common_issue['count']} occurrences")

    for warning in warnings:
        if "aws-exports.js" in warning:
            recommendations.append("Run 'make generate-aws-exports' to update frontend configuration")
        elif "auth_handler.py" in warning:
            recommendations.append("Run 'make generate-lambda-code' to update Lambda function")

    # Add test and lint status summaries
    if e2e_results.get("exit_code") != 0 and e2e_results.get("tests_failed", 0) > 0:
        recommendations.append(
            f"E2E tests: {e2e_results.get('tests_failed', 0)} failed, {e2e_results.get('tests_passed', 0)} passed"
        )

    if not lint_results.get("overall_passed"):
        if not lint_results.get("lint", {}).get("passed"):
            recommendations.append("Linting errors detected - fix before deploying")
        if not lint_results.get("format", {}).get("passed"):
            recommendations.append("Code formatting issues detected - run 'make format'")

    # Add invalidation summary if there are recent ones
    if recent_invalidations:
        recommendations.append(
            f"Recent invalidations: {len(recent_completed)} completed, {len(recent_in_progress)} in progress"
        )

    return recommendations


def main():
    """Main triage function."""
    print_header("Deployment Triage Playbook")

    try:
        analysis = analyze_deployment_status()

        # Print summary
        print_header("Status Summary")

        summary = analysis["summary"]
        if summary["healthy"]:
            print_success("✅ System appears healthy")
        else:
            print_error("❌ Issues detected")

        if summary["issues"]:
            print("\n" + Colors.RED + "Issues:" + Colors.ENDC)
            for issue in summary["issues"]:
                print(f"  • {issue}")

        if summary["warnings"]:
            print("\n" + Colors.YELLOW + "Warnings:" + Colors.ENDC)
            for warning in summary["warnings"]:
                print(f"  • {warning}")

        if summary["recommendations"]:
            print("\n" + Colors.CYAN + "Recommendations:" + Colors.ENDC)
            for rec in summary["recommendations"]:
                print(f"  • {rec}")

        # Show test and lint status details
        print("\n" + Colors.BLUE + "Test & Code Quality Status:" + Colors.ENDC)

        # E2E test status
        e2e_status = summary.get("e2e_status", {})
        if e2e_status.get("passed"):
            print_success("E2E tests: PASSED")
        elif e2e_status.get("exit_code") == 0:
            print_success("E2E tests: COMPLETED")
        else:
            print_error(f"E2E tests: FAILED (exit code {e2e_status.get('exit_code', 'unknown')})")
            if e2e_status.get("tests_failed", 0) > 0:
                print_error(
                    f"  Failed: {e2e_status.get('tests_failed', 0)}, Passed: {e2e_status.get('tests_passed', 0)}"
                )

            # Show failure summary if available
            failure_summary = e2e_status.get("failure_summary", {})
            if failure_summary.get("short_failures"):
                print_error("  Common issues:")
                for short_failure in failure_summary["short_failures"][:2]:
                    print_error(f"    - {short_failure}")

        # Lint status
        lint_status = summary.get("lint_status", {})
        if lint_status.get("overall_passed"):
            print_success("Code quality: PASSED")
        else:
            if not lint_status.get("lint", {}).get("passed"):
                print_error("Linting: FAILED")
                lint_summary = lint_status.get("lint", {}).get("failure_summary", {})
                if lint_summary and lint_summary.get("total_issues", 0) > 0:
                    print_error(f"  {lint_summary['total_issues']} issues found")

            if not lint_status.get("format", {}).get("passed"):
                print_error("Formatting: FAILED")
                format_summary = lint_status.get("format", {}).get("failure_summary", {})
                if format_summary and format_summary.get("total_issues", 0) > 0:
                    print_error(f"  {format_summary['total_issues']} format issues found")

        print(f"\n{Colors.PURPLE}📊 Full analysis saved to: {CACHE_DIR / 'deployment_analysis.json'}{Colors.ENDC}")

        return 0 if summary["healthy"] else 1

    except Exception as e:
        print_error(f"Triage failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
