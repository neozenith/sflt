#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "rich",
#   "boto3",
# ]
# ///
"""Shared utilities for orchestration scripts."""

import json
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from rich.console import Console
from rich.logging import RichHandler

# Constants
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TMP_DIR = PROJECT_ROOT / "tmp"
CACHE_DIR = TMP_DIR / "triage-cache"
DEPLOYMENT_LOG_DIR = TMP_DIR / "deployment-logs"

# Timeout constants for different operations
TIMEOUTS = {
    "default": 30,  # Default command timeout
    "cloudfront": 1200,  # 20 minutes for CloudFront operations
    "lambda_edge": 60,  # 1 minute (fails fast for replicated functions)
    "auth_stack": 300,  # 5 minutes for auth stack operations
    "synthesis": 120,  # 2 minutes for CDK synthesis
}

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEPLOYMENT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure Rich
console = Console()


def configure_logging():
    """Configure Rich logging with standard settings."""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, show_time=False)],
    )
    return logging.getLogger(__name__)


def run_command(
    cmd: str | list[str], check: bool = True, show_output: bool = False, timeout: int = 30
) -> subprocess.CompletedProcess:
    """Run a command with enhanced features.

    Args:
        cmd: Command as a string or list of arguments
        check: Whether to raise exception on non-zero exit
        show_output: Whether to show stdout in real-time
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess with result
    """
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd

    if show_output:
        # Run without capturing for real-time output
        return subprocess.run(cmd_list, check=check, timeout=timeout)
    else:
        return subprocess.run(cmd_list, capture_output=True, text=True, check=check, timeout=timeout)


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


def get_stack_outputs(stack_name: str, region: str, use_cache: bool = True) -> dict[str, Any]:
    """Get CloudFormation stack outputs with optional caching.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        use_cache: Whether to use cached results

    Returns:
        Dictionary with stack outputs and metadata
    """
    cache_file = CACHE_DIR / f"{stack_name}_{region}_outputs.json"

    if use_cache and is_cache_fresh(cache_file, [], max_age_minutes=2):
        return json.loads(cache_file.read_text())

    try:
        cmd = (
            f"aws cloudformation describe-stacks --stack-name {stack_name} "
            f"--region {region} --query 'Stacks[0]' --output json"
        )
        result = run_command(cmd, check=True)

        if result.returncode != 0:
            return {}

        stack_data = json.loads(result.stdout)

        # Parse outputs into key-value pairs
        outputs = {}
        for output in stack_data.get("Outputs", []):
            outputs[output["OutputKey"]] = output["OutputValue"]

        # Add stack metadata
        result_data = {
            "StackName": stack_data.get("StackName"),
            "StackStatus": stack_data.get("StackStatus"),
            "LastUpdatedTime": stack_data.get("LastUpdatedTime"),
            "CreationTime": stack_data.get("CreationTime"),
            "Outputs": outputs,
            "CacheTime": datetime.now().isoformat(),
        }

        # Cache the result
        if use_cache:
            cache_file.write_text(json.dumps(result_data, indent=2))

        return result_data

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗[/red] Failed to get stack outputs for {stack_name}: {e}")
        return {}
    except json.JSONDecodeError as e:
        console.print(f"[red]✗[/red] Failed to parse stack outputs: {e}")
        return {}


def log_deployment_event(event_type: str, details: dict[str, Any]) -> None:
    """Log deployment events for tracking and debugging.

    Args:
        event_type: Type of event (deploy_start, deploy_end, invalidation, etc.)
        details: Event details to log
    """
    timestamp = datetime.now()
    log_file = DEPLOYMENT_LOG_DIR / f"deployment_{timestamp.strftime('%Y%m%d')}.json"

    event = {"timestamp": timestamp.isoformat(), "event_type": event_type, "details": details}

    # Read existing log or create new
    if log_file.exists():
        logs = json.loads(log_file.read_text())
    else:
        logs = []

    logs.append(event)

    # Keep only last 1000 events per file
    if len(logs) > 1000:
        logs = logs[-1000:]

    log_file.write_text(json.dumps(logs, indent=2))


def check_lambda_edge_propagation(lambda_arn: str, last_modified: str) -> dict[str, Any]:
    """Check Lambda@Edge propagation status.

    Args:
        lambda_arn: Lambda function ARN
        last_modified: ISO format timestamp of last modification

    Returns:
        Dictionary with propagation status
    """
    from dateutil import parser

    try:
        modified_dt = parser.parse(last_modified)
        current_dt = datetime.now(modified_dt.tzinfo)
        minutes_since_deploy = (current_dt - modified_dt).total_seconds() / 60

        # Lambda@Edge typically takes 5-30 minutes to propagate
        status = {
            "minutes_since_deploy": round(minutes_since_deploy, 1),
            "is_propagated": minutes_since_deploy > 30,
            "is_propagating": 5 < minutes_since_deploy <= 30,
            "is_fresh": minutes_since_deploy <= 5,
            "estimated_remaining": max(0, 30 - minutes_since_deploy) if minutes_since_deploy < 30 else 0,
        }

        if status["is_propagating"]:
            status["message"] = (
                f"Lambda@Edge is propagating globally ({status['minutes_since_deploy']:.1f} minutes elapsed, "
                f"~{status['estimated_remaining']:.0f} minutes remaining)"
            )
        elif status["is_fresh"]:
            status["message"] = "Lambda@Edge was just deployed, propagation will begin shortly"
        else:
            status["message"] = "Lambda@Edge propagation should be complete"

        return status

    except Exception as e:
        return {"error": str(e), "message": "Unable to determine propagation status"}


def create_cloudfront_invalidation(distribution_id: str, paths: list[str] = None) -> dict[str, Any]:
    """Create CloudFront invalidation.

    Args:
        distribution_id: CloudFront distribution ID
        paths: List of paths to invalidate (default: ["/*"])

    Returns:
        Dictionary with invalidation details
    """
    if paths is None:
        paths = ["/*"]

    try:
        cf_client = boto3.client("cloudfront")

        response = cf_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(paths), "Items": paths},
                "CallerReference": f"orchestrator-{datetime.now().timestamp()}",
            },
        )

        invalidation = response["Invalidation"]

        result = {
            "Id": invalidation["Id"],
            "Status": invalidation["Status"],
            "CreateTime": invalidation["CreateTime"].isoformat(),
            "Paths": paths,
        }

        # Log the invalidation
        log_deployment_event(
            "cloudfront_invalidation",
            {"distribution_id": distribution_id, "invalidation_id": result["Id"], "paths": paths},
        )

        return result

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create invalidation: {e}")
        return {"error": str(e)}


def wait_for_propagation(lambda_arn: str, last_modified: str, max_wait_minutes: int = 35) -> bool:
    """Wait for Lambda@Edge propagation with progress updates.

    Args:
        lambda_arn: Lambda function ARN
        last_modified: ISO format timestamp of last modification
        max_wait_minutes: Maximum time to wait

    Returns:
        True if propagation complete, False if timeout
    """
    start_time = time.time()

    with console.status("[yellow]Waiting for Lambda@Edge propagation...[/yellow]") as status:
        while True:
            propagation_status = check_lambda_edge_propagation(lambda_arn, last_modified)

            if propagation_status.get("is_propagated"):
                console.print("[green]✓[/green] Lambda@Edge propagation complete")
                return True

            elapsed = (time.time() - start_time) / 60
            if elapsed > max_wait_minutes:
                console.print(f"[yellow]⚠️[/yellow] Propagation timeout after {elapsed:.1f} minutes")
                return False

            # Update status message
            remaining = propagation_status.get("estimated_remaining", 0)
            status.update(
                f"[yellow]Waiting for Lambda@Edge propagation... (~{remaining:.0f} minutes remaining)[/yellow]"
            )

            # Check every 30 seconds
            time.sleep(30)


def deploy_with_retry(
    command: str, stack_name: str, max_retries: int = 2, show_output: bool = True, timeout: int = 30
) -> subprocess.CompletedProcess | None:
    """Deploy a stack with retry logic for transient failures.

    Args:
        command: Deployment command to run
        stack_name: Stack name for logging
        max_retries: Maximum number of retries
        show_output: Whether to show command output

    Returns:
        CompletedProcess or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            log_deployment_event(
                "deploy_attempt", {"stack_name": stack_name, "attempt": attempt + 1, "command": command}
            )

            result = run_command(command, check=False, show_output=show_output, timeout=timeout)

            if result.returncode == 0:
                log_deployment_event("deploy_success", {"stack_name": stack_name, "attempt": attempt + 1})
                return result

            # Check for specific retryable errors
            error_output = result.stderr if hasattr(result, "stderr") and result.stderr else ""
            retryable_errors = ["rate exceeded", "throttling", "timeout", "connection reset"]

            is_retryable = any(err in error_output.lower() for err in retryable_errors)

            if is_retryable and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # Exponential backoff
                console.print(
                    f"[yellow]Retryable error detected. Waiting {wait_time}s "
                    f"before retry {attempt + 2}/{max_retries}...[/yellow]"
                )
                time.sleep(wait_time)
                continue
            else:
                log_deployment_event(
                    "deploy_failure", {"stack_name": stack_name, "attempt": attempt + 1, "error": error_output}
                )
                return result

        except Exception as e:
            console.print(f"[red]✗[/red] Deployment error: {e}")
            if attempt < max_retries - 1:
                continue
            raise

    return None
