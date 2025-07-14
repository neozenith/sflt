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

import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Add any constants here
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

def main():
    """Main function."""
    # Script logic here
    logger.info("Script starting...")
    # Use logger.info(), logger.warning(), logger.error() for output
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 4. Rich Logging Conventions

#### Rich Setup

All scripts use the Rich library for enhanced colored output. The setup combines Rich's Console for colored markup with Python's logging for plain messages:

```python
import logging
import sys
from rich.console import Console
from rich.logging import RichHandler

# Configure Rich
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)
```

#### Output Patterns

Use the appropriate method for different message types:

- **`console.print()`** - For messages with Rich markup and colors
- **`logger.info()`** - For plain informational messages
- **`logger.warning()`** - For plain warning messages  
- **`logger.error()`** - For plain error messages

#### Rich Markup Patterns

**Success Messages:**
```python
console.print("[green]✓[/green] Operation completed successfully")
console.print(f"[green]✓[/green] Generated [cyan]{file_count}[/cyan] files")
```

**Error Messages:**
```python
console.print("[red]✗[/red] Failed to connect to AWS service")
console.print(f"[red]✗[/red] Missing required value: [yellow]{param_name}[/yellow]")
```

**Warning Messages:**
```python
console.print("[yellow]Configuration drift detected[/yellow]")
console.print(f"[yellow]Retrying operation in {delay} seconds[/yellow]")
```

**Information with Highlighting:**
```python
console.print(f"  [cyan]User Pool ID:[/cyan] [yellow]{pool_id}[/yellow]")
console.print(f"[dim]Processing {item_count} items...[/dim]")
```

**Plain Messages (no markup):**
```python
logger.info("Found credentials in shared credentials file: ~/.aws/credentials")
logger.warning("PKCE requirement cannot be checked via API")
logger.error(f"Failed to get stack outputs for {stack_name}: {e}")
```

#### Headers and Sections

Use Rich's `console.rule()` for professional section headers:

```python
console.rule("[bold magenta]Section Title[/bold magenta]")
console.rule("[bold blue]Configuration Check[/bold blue]")
console.rule("[bold green]Test Results[/bold green]")
```

#### Advanced Rich Features

**Links and URLs:**
```python
logger.info(f"Visit: [link]https://example.com[/link]")
```

**Syntax Highlighting:**
```python
from rich.syntax import Syntax
syntax = Syntax(code_content, "python", theme="monokai")
console.print(syntax)
```

**Tables for Structured Data:**
```python
from rich.table import Table
table = Table(title="Configuration Summary")
table.add_column("Key", style="cyan")
table.add_column("Value", style="yellow")
table.add_row("User Pool ID", pool_id)
console.print(table)
```

#### Example Rich Output Patterns

```python
# Headers
console.rule("[bold magenta]AWS Configuration Check[/bold magenta]")

# Success with context
logger.info("[green]✓[/green] Found User Pool ID: [cyan]ap-southeast-2_abc123[/cyan]")

# Warnings with highlighting
logger.warning("[yellow]Configuration drift:[/yellow] [red]old_value[/red] → [green]new_value[/green]")

# Errors with context
logger.error("[red]✗[/red] Missing required outputs: [yellow]UserPoolId, ClientId[/yellow]")

# Information with structure
logger.info("[bold]Template variables:[/bold]")
logger.info(f"  [cyan]COGNITO_DOMAIN:[/cyan] [yellow]{domain}[/yellow]")

# Links and interactive elements
logger.info("CloudFront domain: [link]https://d123.cloudfront.net[/link]")
```

#### Rich Dependencies

Each script includes Rich in its PEP-723 dependencies:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
```

### 5. Common Patterns

#### AWS Profile Handling

Scripts that interact with AWS should respect the `AWS_PROFILE` environment variable:

```python
import os
# AWS SDK will automatically use AWS_PROFILE if set
# No need to manually configure it
```

### 6. Error Handling

Scripts should return appropriate exit codes:
- `0` - Success
- `1` - General error
- `2` - Special condition (e.g., configuration drift detected)

### 7. Documentation

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