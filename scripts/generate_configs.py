#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Generate both aws-exports.js and Lambda@Edge code from stack outputs."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our modules directly
# Import the generation functions directly
from generate_aws_exports import generate_aws_exports
from generate_lambda_code import generate_lambda_code_from_template
from orchestration_utils import configure_logging, console

from cdk.config import get_deployment_config

logger = configure_logging()


def main():
    """Generate configuration files from stack outputs."""
    config = get_deployment_config()

    console.rule("[bold magenta]Configuration Generator[/bold magenta]")
    console.print(f"🔧 Generating configs for branch: [cyan]{config.branch}[/cyan]")
    console.print(f"📦 Stack prefix: [yellow]{config.stack_prefix}[/yellow]")
    console.print()

    # Generate aws-exports.js
    console.print("[dim]Generating aws-exports.js...[/dim]")
    try:
        aws_exports_success = generate_aws_exports()
        if aws_exports_success:
            console.print("[green]✓[/green] aws-exports.js generated successfully")
        else:
            console.print("[yellow]⚠[/yellow] aws-exports.js generation failed (may be normal if stacks don't exist)")
    except Exception as e:
        console.print(f"[red]✗[/red] aws-exports.js generation failed with error: {e}")
        aws_exports_success = False

    # Generate Lambda code
    console.print("[dim]Generating Lambda@Edge code...[/dim]")
    try:
        lambda_code_success = generate_lambda_code_from_template()
        if lambda_code_success:
            console.print("[green]✓[/green] Lambda@Edge code generated successfully")
        else:
            console.print("[yellow]⚠[/yellow] Lambda@Edge code generation failed (may be normal if stacks don't exist)")
    except Exception as e:
        console.print(f"[red]✗[/red] Lambda@Edge code generation failed with error: {e}")
        lambda_code_success = False

    console.print()

    if aws_exports_success and lambda_code_success:
        console.print("[green]✅[/green] All configuration files generated successfully")
        return 0
    elif aws_exports_success or lambda_code_success:
        console.print("[yellow]⚠️[/yellow] Some configuration files generated (partial success)")
        console.print("[dim]This is normal if stacks are not fully deployed yet[/dim]")
        return 0
    else:
        console.print("[yellow]⚠️[/yellow] Configuration generation failed")
        console.print("[dim]This is normal for first deployment - run after stacks are deployed[/dim]")
        return 0  # Return 0 to not fail the deployment process


if __name__ == "__main__":
    sys.exit(main())
