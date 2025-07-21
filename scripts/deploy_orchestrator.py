#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Orchestrate CDK deployment with automatic configuration convergence."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared utilities
from orchestration_utils import (
    check_lambda_edge_propagation,
    configure_logging,
    console,
    deploy_with_retry,
    get_stack_outputs,
    log_deployment_event,
)

from cdk.config import get_deployment_config

logger = configure_logging()


def check_lambda_needs_update() -> bool:
    """Check if Lambda@Edge code needs to be regenerated."""
    template_path = Path("cdk/lambda-edge/auth_handler.py.template")
    generated_path = Path("cdk/lambda-edge/auth_handler.py")

    if not template_path.exists():
        return False

    if not generated_path.exists():
        return True

    return template_path.stat().st_mtime > generated_path.stat().st_mtime


def main():
    """Main deployment orchestration logic."""
    config = get_deployment_config()

    console.rule("[bold blue]CDK Deployment Orchestrator[/bold blue]")
    console.print(f"🚀 Deploying branch: [cyan]{config.branch}[/cyan]")
    console.print(f"📦 Stack prefix: [yellow]{config.stack_prefix}[/yellow]")
    console.print()

    # Log deployment start
    log_deployment_event(
        "deployment_start",
        {"branch": config.branch, "stack_prefix": config.stack_prefix, "environment": config.environment},
    )

    # Phase 1: Initial deployment
    console.print("[bold]Phase 1: Initial deployment...[/bold]")

    result = deploy_with_retry("uv run cdk deploy --all --require-approval never", "all stacks", show_output=True)

    if result and result.returncode == 0:
        console.print("[green]✓[/green] Initial deployment successful")
    else:
        console.print("[red]✗[/red] Initial deployment failed")
        log_deployment_event("deployment_failed", {"phase": "initial"})
        return 1

    console.print()

    # Phase 2: Configuration convergence
    console.print("[bold]Phase 2: Configuration convergence...[/bold]")

    # Import and run the config generation directly
    try:
        from generate_configs import main as generate_configs_main

        config_exit_code = generate_configs_main()
        config_success = config_exit_code == 0
    except Exception as e:
        console.print(f"[yellow]⚠️[/yellow] Config generation error: {e}")
        config_success = False

    if config_success:
        console.print("[green]✓[/green] Configurations generated successfully")

        # Phase 3: Check if Lambda@Edge needs update
        console.print()
        console.print("[bold]Phase 3: Checking for Lambda@Edge updates...[/bold]")

        if check_lambda_needs_update():
            console.print("📦 Lambda@Edge code changed, redeploying site stack...")

            result = deploy_with_retry(
                f"uv run cdk deploy {config.stack_prefix}-site --require-approval never",
                f"{config.stack_prefix}-site",
                show_output=True,
            )

            if result and result.returncode == 0:
                console.print("[green]✓[/green] Site stack redeployment successful")

                # Get Lambda function info for tracking
                site_outputs = get_stack_outputs(config.static_site_stack_name, config.site_region)
                lambda_arn = site_outputs.get("Outputs", {}).get("AuthLambdaArn")

                if lambda_arn:
                    console.print()
                    console.print("[bold]Phase 4: Lambda@Edge propagation status...[/bold]")

                    # Check propagation status
                    last_modified = datetime.now().isoformat()
                    propagation_status = check_lambda_edge_propagation(lambda_arn, last_modified)

                    console.print(
                        f"[yellow]⏱️  {propagation_status.get('message', 'Checking propagation status...')}[/yellow]"
                    )

                    # Log Lambda deployment
                    log_deployment_event(
                        "lambda_edge_deployed",
                        {
                            "lambda_arn": lambda_arn,
                            "last_modified": last_modified,
                            "propagation_status": propagation_status,
                        },
                    )

                    # Ask if we should create CloudFront invalidation
                    console.print("\n[bold]CloudFront Cache Invalidation[/bold]")
                    console.print("Would you like to invalidate CloudFront cache?")
                    console.print("[dim]This will force CloudFront to fetch the latest Lambda@Edge function[/dim]")

                    dist_id = site_outputs.get("Outputs", {}).get("DistributionId")
                    if dist_id:
                        console.print("\n[dim]Run manually if needed:[/dim]")
                        console.print(
                            f"[cyan]aws cloudfront create-invalidation --distribution-id {dist_id} --paths '/*'[/cyan]"
                        )

                console.print("\n[green]✅[/green] Deployment complete with convergence")
            else:
                console.print("[red]✗[/red] Site stack redeployment failed")
                log_deployment_event("deployment_failed", {"phase": "site_stack"})
                return 1
        else:
            console.print("[green]✓[/green] No Lambda@Edge updates needed")
            console.print("[green]✅[/green] Deployment complete")
    else:
        console.print("[yellow]⚠️[/yellow]  Configuration generation failed (this is normal for first deployment)")
        console.print("[green]✓[/green] Initial deployment complete")
        console.print()
        console.print("[dim]ℹ️  Run 'make generate-configs' after deployment to generate configuration files[/dim]")

    # Log deployment end
    log_deployment_event(
        "deployment_end",
        {"success": True, "config_generated": config_success, "lambda_updated": check_lambda_needs_update()},
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
