#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Enhanced CDK stack destruction with Lambda@Edge handling."""

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import boto3

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared utilities
from orchestration_utils import TIMEOUTS, configure_logging, console, log_deployment_event, run_command

from cdk.config import get_deployment_config

logger = configure_logging()


@dataclass
class DestroyResult:
    """Result of a stack destruction attempt."""

    success: bool
    lambda_edge_blocked: bool = False
    in_progress: bool = False
    error_message: str = ""


def main():
    """Enhanced stack destruction with Lambda@Edge handling."""
    config = get_deployment_config()

    console.rule("[bold red]Enhanced CDK Stack Destroyer[/bold red]")
    console.print(f"🗑️  Destroying branch: [cyan]{config.branch}[/cyan]")
    console.print(f"📦 Stack prefix: [yellow]{config.stack_prefix}[/yellow]")
    console.print()

    # Log destruction start
    log_deployment_event(
        "destruction_start",
        {"branch": config.branch, "stack_prefix": config.stack_prefix, "environment": config.environment},
    )

    # Confirm destruction for production environments
    if config.environment == "prod":
        console.print("[bold red]⚠️  WARNING: You are about to destroy PRODUCTION resources![/bold red]")
        confirm = console.input("Type 'destroy-prod' to confirm: ")
        if confirm != "destroy-prod":
            console.print("❌ Destruction cancelled")
            log_deployment_event("destruction_cancelled", {"reason": "user_cancelled"})
            return 0

    # Phase 1: Check for Lambda@Edge functions
    lambda_edge_functions = detect_lambda_edge_functions(config)

    if lambda_edge_functions:
        console.print("[yellow]⚠️  Lambda@Edge functions detected:[/yellow]")
        for func in lambda_edge_functions:
            console.print(f"   • {func}")
        console.print("[dim]These require 24-48h for global replication cleanup[/dim]")
        console.print()

    # Phase 2: Individual stack destruction with proper timeouts
    result = destroy_stacks_individually(config, lambda_edge_functions)

    # Phase 3: Handle results and create cleanup reminders
    if result == "partial_success":
        create_cleanup_reminder(config, lambda_edge_functions)
        console.print()
        console.print("[yellow]✓[/yellow] Partial cleanup completed")
        console.print("[yellow]⏳[/yellow] Run cleanup again in 24-48 hours for Lambda@Edge")
        return 2  # Special exit code for partial success

    elif result == "complete":
        console.print("[green]✓[/green] Complete stack destruction successful")
        log_deployment_event("destruction_completed", {"success": True})
        return 0

    else:
        console.print("[red]✗[/red] Stack destruction failed")
        log_deployment_event("destruction_failed", {"success": False})
        return 1


def detect_lambda_edge_functions(config) -> list[str]:
    """Detect Lambda@Edge functions in the stacks."""
    functions = []
    try:
        # Check if site stack exists and has Lambda@Edge
        cf_client = boto3.client("cloudformation", region_name=config.site_region)
        response = cf_client.describe_stack_resources(StackName=config.static_site_stack_name)

        for resource in response["StackResources"]:
            if resource["ResourceType"] == "AWS::Lambda::Function":
                # Check if it's Lambda@Edge by looking at function config
                try:
                    lambda_client = boto3.client("lambda", region_name=config.site_region)
                    func_config = lambda_client.get_function(FunctionName=resource["PhysicalResourceId"])

                    # Lambda@Edge functions have specific characteristics
                    config_data = func_config.get("Configuration", {})

                    # Check if function has versions (Lambda@Edge creates versions)
                    versions_response = lambda_client.list_versions_by_function(
                        FunctionName=resource["PhysicalResourceId"]
                    )

                    if len(versions_response.get("Versions", [])) > 1:  # More than $LATEST
                        functions.append(resource["PhysicalResourceId"])

                except Exception as e:
                    logger.warning(f"Could not check Lambda function {resource['PhysicalResourceId']}: {e}")

    except Exception as e:
        logger.warning(f"Could not detect Lambda@Edge functions: {e}")

    return functions


def destroy_stacks_individually(config, lambda_edge_functions: list[str]) -> str:
    """Destroy stacks one by one with appropriate error handling."""
    console.print("[bold]Phase 1: Attempting site stack destruction[/bold]")
    site_result = destroy_site_stack(config)

    console.print("\n[bold]Phase 2: Attempting auth stack destruction[/bold]")
    auth_result = destroy_auth_stack(config)

    # Analyze results
    if site_result.lambda_edge_blocked and auth_result.success:
        console.print("\n[yellow]📊 Destruction Summary:[/yellow]")
        console.print("[green]✓[/green] Auth stack destroyed successfully")
        console.print("[yellow]⏳[/yellow] Site stack blocked by Lambda@Edge replication")
        return "partial_success"

    elif site_result.success and auth_result.success:
        console.print("\n[green]📊 Destruction Summary:[/green]")
        console.print("[green]✓[/green] Both stacks destroyed successfully")
        return "complete"

    elif site_result.in_progress:
        console.print("\n[yellow]📊 Destruction Summary:[/yellow]")
        console.print("[yellow]⏳[/yellow] CloudFront deletion still in progress")
        console.print("[yellow]ℹ️[/yellow] This may take 15-20 minutes to complete")
        if auth_result.success:
            console.print("[green]✓[/green] Auth stack destroyed successfully")
        return "partial_success" if auth_result.success else "failed"

    else:
        console.print("\n[red]📊 Destruction Summary:[/red]")
        console.print(f"[red]✗[/red] Site stack failed: {site_result.error_message}")
        console.print(f"[red]✗[/red] Auth stack failed: {auth_result.error_message}")
        return "failed"


def destroy_site_stack(config) -> DestroyResult:
    """Destroy site stack with extended timeout for CloudFront."""
    try:
        console.print("🔄 Destroying site stack (may take 15-20 minutes for CloudFront)...")

        result = run_command(
            f"uv run cdk destroy {config.static_site_stack_name} --force",
            check=False,
            show_output=True,
            timeout=TIMEOUTS["cloudfront"],  # 20 minutes
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Site stack destroyed successfully")
            return DestroyResult(success=True)
        else:
            error_msg = result.stderr if hasattr(result, "stderr") and result.stderr else "Unknown error"
            if "replicated function" in error_msg:
                console.print("[yellow]⏳[/yellow] Site stack blocked by Lambda@Edge replication")
                return DestroyResult(success=False, lambda_edge_blocked=True, error_message=error_msg)
            else:
                console.print(f"[red]✗[/red] Site stack destruction failed: {error_msg}")
                return DestroyResult(success=False, error_message=error_msg)

    except subprocess.TimeoutExpired:
        console.print("[yellow]⏳[/yellow] CloudFront deletion still in progress (timed out after 20 min)")
        return DestroyResult(success=False, in_progress=True, error_message="Timeout - operation in progress")
    except Exception as e:
        error_msg = str(e)
        if "replicated function" in error_msg:
            return DestroyResult(success=False, lambda_edge_blocked=True, error_message=error_msg)
        console.print(f"[red]✗[/red] Unexpected error destroying site stack: {error_msg}")
        return DestroyResult(success=False, error_message=error_msg)


def destroy_auth_stack(config) -> DestroyResult:
    """Destroy auth stack (should succeed independently)."""
    try:
        console.print("🔄 Destroying auth stack...")

        result = run_command(
            f"uv run cdk destroy {config.auth_stack_name} --force",
            check=False,
            show_output=True,
            timeout=TIMEOUTS["auth_stack"],  # 5 minutes
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Auth stack destroyed successfully")
            return DestroyResult(success=True)
        else:
            error_msg = result.stderr if hasattr(result, "stderr") and result.stderr else "Unknown error"
            console.print(f"[red]✗[/red] Auth stack destruction failed: {error_msg}")
            return DestroyResult(success=False, error_message=error_msg)

    except subprocess.TimeoutExpired:
        console.print("[red]✗[/red] Auth stack destruction timed out after 5 minutes")
        return DestroyResult(success=False, error_message="Timeout after 5 minutes")
    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]✗[/red] Unexpected error destroying auth stack: {error_msg}")
        return DestroyResult(success=False, error_message=error_msg)


def create_cleanup_reminder(config, lambda_edge_functions: list[str]):
    """Create a reminder script for future cleanup."""
    from orchestration_utils import PROJECT_ROOT, TMP_DIR

    reminder_script = TMP_DIR / f"cleanup_reminder_{config.branch.replace('/', '_').replace('-', '_')}.sh"

    script_content = f"""#!/bin/bash
# Auto-generated cleanup reminder for {config.branch}
# Created: {datetime.now().isoformat()}
# Lambda@Edge functions: {", ".join(lambda_edge_functions)}

echo "🗑️  Retrying cleanup for branch: {config.branch}"
echo "⏰ Lambda@Edge functions should be deletable after 24-48h"
echo ""

export AWS_PROFILE={config.aws_profile}
export GIT_BRANCH={config.branch}

cd {PROJECT_ROOT}

echo "🔄 Running enhanced destroy orchestrator..."
make destroy

if [ $? -eq 0 ]; then
    echo "✅ Cleanup completed successfully!"
    echo "🗑️  Removing this reminder script..."
    rm "$0"
else
    echo "❌ Cleanup still failed. Lambda@Edge may need more time."
    echo "💡 Try again tomorrow or delete stacks manually via AWS Console"
fi
"""

    with open(reminder_script, "w") as f:
        f.write(script_content)

    reminder_script.chmod(0o755)

    future_date = datetime.now() + timedelta(hours=48)
    console.print()
    console.print("[cyan]💡 Cleanup reminder created:[/cyan]")
    console.print(f"   📁 {reminder_script}")
    console.print(f"   ⏰ Run after: [yellow]{future_date.strftime('%Y-%m-%d %H:%M')}[/yellow]")
    console.print(f"   🚀 Command: [cyan]{reminder_script}[/cyan]")


if __name__ == "__main__":
    sys.exit(main())
