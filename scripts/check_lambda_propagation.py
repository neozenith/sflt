#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
#   "python-dateutil",
# ]
# ///
"""Check Lambda@Edge propagation status and provide context for deployment timing."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared utilities
import json

import boto3
from orchestration_utils import (
    DEPLOYMENT_LOG_DIR,
    check_lambda_edge_propagation,
    configure_logging,
    console,
    get_stack_outputs,
)

from cdk.config import get_deployment_config

logger = configure_logging()


def get_latest_deployment_events() -> list[dict]:
    """Get recent deployment events from logs."""
    events = []

    # Check today's and yesterday's logs
    for days_back in [0, 1]:
        log_date = datetime.now()
        if days_back > 0:
            from datetime import timedelta

            log_date = log_date - timedelta(days=days_back)

        log_file = DEPLOYMENT_LOG_DIR / f"deployment_{log_date.strftime('%Y%m%d')}.json"

        if log_file.exists():
            try:
                logs = json.loads(log_file.read_text())
                events.extend(logs)
            except Exception as e:
                logger.warning(f"Failed to read deployment log {log_file}: {e}")

    # Sort by timestamp (most recent first)
    events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return events


def analyze_lambda_deployment_timing() -> dict:
    """Analyze recent Lambda deployments and their timing."""
    events = get_latest_deployment_events()

    analysis = {"recent_deployments": [], "lambda_edge_deployments": [], "invalidations": [], "recommendations": []}

    # Find recent deployment and lambda events
    for event in events:
        event_type = event.get("event_type", "")
        timestamp = event.get("timestamp", "")
        details = event.get("details", {})

        if event_type == "deployment_start":
            analysis["recent_deployments"].append(
                {"timestamp": timestamp, "branch": details.get("branch"), "stack_prefix": details.get("stack_prefix")}
            )
        elif event_type == "lambda_edge_deployed":
            analysis["lambda_edge_deployments"].append(
                {
                    "timestamp": timestamp,
                    "lambda_arn": details.get("lambda_arn"),
                    "propagation_status": details.get("propagation_status", {}),
                }
            )
        elif event_type == "cloudfront_invalidation":
            analysis["invalidations"].append(
                {
                    "timestamp": timestamp,
                    "distribution_id": details.get("distribution_id"),
                    "invalidation_id": details.get("invalidation_id"),
                }
            )

    # Generate recommendations based on timing
    now = datetime.now()

    if analysis["lambda_edge_deployments"]:
        latest_lambda = analysis["lambda_edge_deployments"][0]
        lambda_timestamp = datetime.fromisoformat(
            latest_lambda["timestamp"].replace("Z", "+00:00").replace("+00:00", "")
        )
        minutes_elapsed = (now - lambda_timestamp).total_seconds() / 60

        if minutes_elapsed < 5:
            analysis["recommendations"].append(
                f"Lambda@Edge deployed {minutes_elapsed:.1f} minutes ago. "
                f"Propagation just started - wait a few more minutes."
            )
        elif minutes_elapsed < 30:
            remaining = 30 - minutes_elapsed
            analysis["recommendations"].append(
                f"Lambda@Edge deployed {minutes_elapsed:.1f} minutes ago. "
                f"Still propagating globally (~{remaining:.0f} minutes remaining)."
            )
        else:
            analysis["recommendations"].append(
                f"Lambda@Edge deployed {minutes_elapsed:.1f} minutes ago. Propagation should be complete."
            )

    return analysis


def check_current_lambda_status():
    """Check current Lambda function status."""
    config = get_deployment_config()

    console.print("[bold]Current Lambda@Edge Status[/bold]")

    # Get stack outputs
    site_outputs = get_stack_outputs(config.static_site_stack_name, config.site_region)
    if not site_outputs:
        console.print("[red]✗[/red] Could not fetch site stack outputs")
        return

    lambda_arn = site_outputs.get("Outputs", {}).get("AuthLambdaArn")
    if not lambda_arn:
        console.print("[red]✗[/red] No Lambda@Edge ARN found in stack outputs")
        return

    console.print(f"[cyan]Lambda ARN:[/cyan] {lambda_arn}")

    # Get function details
    try:
        lambda_client = boto3.client("lambda", region_name="us-east-1")
        response = lambda_client.get_function(FunctionName=lambda_arn)
        config_info = response["Configuration"]

        last_modified = config_info["LastModified"]
        console.print(f"[cyan]Last Modified:[/cyan] {last_modified}")

        # Check propagation status
        propagation_status = check_lambda_edge_propagation(lambda_arn, last_modified)

        if propagation_status.get("is_propagated"):
            console.print("[green]✓[/green] Lambda@Edge propagation complete")
        elif propagation_status.get("is_propagating"):
            remaining = propagation_status.get("estimated_remaining", 0)
            console.print(f"[yellow]⏱️[/yellow] Lambda@Edge propagating (~{remaining:.0f} minutes remaining)")
        else:
            console.print("[blue]ℹ️[/blue] Lambda@Edge was just deployed, propagation starting")

        console.print(f"[dim]{propagation_status.get('message', '')}[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to check Lambda function: {e}")


def main():
    """Main function to check Lambda@Edge propagation status."""
    console.rule("[bold magenta]Lambda@Edge Propagation Checker[/bold magenta]")

    # Check current Lambda status
    check_current_lambda_status()

    console.print()

    # Analyze deployment timing
    console.print("[bold]Recent Deployment Activity[/bold]")
    analysis = analyze_lambda_deployment_timing()

    if analysis["recent_deployments"]:
        console.print(f"[green]✓[/green] Found {len(analysis['recent_deployments'])} recent deployments")
        for deployment in analysis["recent_deployments"][:3]:  # Show last 3
            timestamp = deployment["timestamp"][:19]  # Remove microseconds
            console.print(f"  [dim]{timestamp}[/dim] - Branch: [cyan]{deployment['branch']}[/cyan]")

    if analysis["lambda_edge_deployments"]:
        console.print(f"[green]✓[/green] Found {len(analysis['lambda_edge_deployments'])} Lambda@Edge deployments")
        for deployment in analysis["lambda_edge_deployments"][:2]:  # Show last 2
            timestamp = deployment["timestamp"][:19]
            console.print(f"  [dim]{timestamp}[/dim] - Lambda deployed")

    if analysis["invalidations"]:
        console.print(f"[green]✓[/green] Found {len(analysis['invalidations'])} CloudFront invalidations")
        for invalidation in analysis["invalidations"][:2]:  # Show last 2
            timestamp = invalidation["timestamp"][:19]
            console.print(f"  [dim]{timestamp}[/dim] - Invalidation created")

    # Show recommendations
    if analysis["recommendations"]:
        console.print("\n[bold yellow]Recommendations[/bold yellow]")
        for rec in analysis["recommendations"]:
            console.print(f"  💡 {rec}")

    # Provide helpful commands
    console.print("\n[bold]Helpful Commands[/bold]")
    console.print("[cyan]make triage[/cyan] - Run comprehensive deployment triage")
    console.print("[cyan]make test-e2e[/cyan] - Test current deployment end-to-end")
    console.print("[cyan]make outputs[/cyan] - Show current stack outputs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
