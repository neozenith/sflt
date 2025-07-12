# Scripts Directory Guidelines

This directory contains utility scripts for the SFLT project. All scripts must follow these guidelines.

## Script Requirements

### 1. PEP-723 Compliance

All Python scripts in this directory MUST be compliant with [PEP-723](https://peps.python.org/pep-0723/) for inline script dependencies.

Each script should include its dependencies in a TOML block at the top of the file:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "python-dotenv",
#   "requests",
# ]
# ///
"""Script description here."""

import boto3
from dotenv import load_dotenv
# ... rest of the script
```

### 2. Script Execution

Scripts should always be executed using `uv run` to ensure dependencies are properly resolved:

```bash
uv run scripts/script_name_here.py
```

This allows `uv` to:
- Parse the inline dependencies
- Create an isolated environment
- Install required packages
- Execute the script

### 3. Script Structure

All scripts should follow this structure:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "package-name==version",  # Pin versions when needed
# ]
# ///
"""One-line description of what the script does.

More detailed description if needed.
"""

import sys
from pathlib import Path

# Add any constants here
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

def main():
    """Main function."""
    # Script logic here
    pass

if __name__ == "__main__":
    sys.exit(main())
```

### 4. Common Patterns

#### Colors for Terminal Output

```python
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
```

#### AWS Profile Handling

Scripts that interact with AWS should respect the `AWS_PROFILE` environment variable:

```python
import os
# AWS SDK will automatically use AWS_PROFILE if set
# No need to manually configure it
```

### 5. Error Handling

Scripts should return appropriate exit codes:
- `0` - Success
- `1` - General error
- `2` - Special condition (e.g., configuration drift detected)

### 6. Documentation

Each script should have:
- A module-level docstring explaining its purpose
- Function docstrings for non-trivial functions
- Comments for complex logic

## Current Scripts

- `generate_aws_exports.py` - Generates frontend configuration from CDK stack outputs
- `generate_lambda_code.py` - Generates Lambda@Edge code from template with CDK values
- `diagnose_oauth.py` - Diagnoses OAuth configuration issues
- `test_convergence.py` - Tests configuration drift detection
- `triage_deployment.py` - Comprehensive deployment triage with AWS status, e2e tests, and code quality checks

## Template System

Some files in the project use a template system to inject dynamic values at build time:

### Lambda@Edge Template

`cdk/lambda-edge/auth_handler.py.template` → `cdk/lambda-edge/auth_handler.py`

The Lambda@Edge function uses template variables that are replaced with actual values from CDK stack outputs:

- `{{COGNITO_DOMAIN}}` - Cognito domain for OAuth redirects
- `{{COGNITO_CLIENT_ID}}` - User Pool Client ID
- `{{COGNITO_REGION}}` - AWS region for Cognito
- `{{USER_POOL_ID}}` - User Pool ID for JWT validation

This allows the Lambda function to be environment-agnostic and reusable across different deployments.

### Frontend Configuration

`frontend/src/aws-exports.js` is generated from CDK stack outputs, not from a template file.

## Triage and Caching System

The `triage_deployment.py` script provides comprehensive deployment status analysis with intelligent caching:

### Cache Files Location
All cache files are stored in `tmp/triage-cache/` with JSON format:
- `{stack_name}_{region}_outputs.json` - CloudFormation stack outputs
- `{function_name}_lambda_status.json` - Lambda function status and code analysis
- `{distribution_id}_cloudfront_status.json` - CloudFront distribution status
- `endpoint_test_*.json` - HTTP endpoint test results
- `e2e_test_results.json` - E2E test results
- `lint_check_results.json` - Lint and format check results
- `deployment_analysis.json` - Full deployment analysis
- `combined_outputs.json` - Combined stack outputs (used by `make outputs`)

### Cache Freshness
Caches are considered fresh based on:
- **Stack outputs**: 2 minutes max age
- **Lambda status**: 5 minutes max age, invalidated when source files change
- **CloudFront status**: 2 minutes max age
- **Endpoint tests**: 1 minute max age
- **E2E tests**: 1 minute max age (deployment-dependent)
- **Lint checks**: 5 minutes max age, invalidated when source files change
- **Combined outputs**: 2 minutes max age

### Source File Dependencies
Lambda status cache tracks these source files:
- `cdk/lambda-edge/auth_handler.py` - Generated function code
- `cdk/lambda-edge/auth_handler.py.template` - Template file

Lint checks cache tracks these source files:
- `app.py` - CDK app entry point
- `cdk/` - CDK infrastructure code
- `scripts/` - All scripts
- `tests/` - Python unit tests
- `frontend/src/` - Frontend source code
- `pyproject.toml` - Python project configuration

When any source file is newer than the cache, the cache is invalidated.

### Comprehensive Status Checks
The triage script now performs:
1. **AWS Infrastructure**: CloudFormation stacks, Lambda functions, CloudFront distributions
2. **Configuration Drift**: Checks for outdated generated files
3. **E2E Tests**: Runs full end-to-end test suite against deployed CloudFront
4. **Code Quality**: Runs linting and format checks on all code
5. **Endpoint Testing**: Tests actual HTTP responses from deployed services

## Adding New Scripts

1. Create the script with proper PEP-723 headers
2. Make it executable: `chmod +x scripts/new_script.py`
3. Test it with: `uv run scripts/new_script.py`
4. Update this list with a description of the new script
5. If the script is used in the Makefile, use the `uv run` format there too