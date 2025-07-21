#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Enhanced cleanup for old feature branch CDK stacks with Lambda@Edge retry logic."""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta

import boto3
from rich.console import Console
from rich.table import Table

console = Console()


def main():
    """Enhanced cleanup with support for Lambda@Edge retries."""
    parser = argparse.ArgumentParser(description="Cleanup feature branch stacks")
    parser.add_argument("--lambda-edge-retry", action="store_true", help="Include Lambda@Edge blocked stacks for retry")
    parser.add_argument("--list-blocked", action="store_true", help="List Lambda@Edge blocked stacks only")
    parser.add_argument(
        "--include-lambda-edge-retry", action="store_true", help="Include both old stacks and Lambda@Edge retries"
    )

    args = parser.parse_args()

    if args.list_blocked:
        list_blocked_stacks()
        return 0

    console.rule("[bold red]Enhanced Feature Branch Cleanup[/bold red]")

    # Get active branches
    active_branches = get_active_git_branches()
    console.print(f"Active branches: {', '.join(active_branches)}")

    # Find stacks in both regions
    regions = ["ap-southeast-2", "us-east-1"]
    old_stacks = []
    lambda_edge_retry_stacks = []

    for region in regions:
        if args.lambda_edge_retry or args.include_lambda_edge_retry:
            # Only look for Lambda@Edge retry stacks
            retry_stacks = find_lambda_edge_retry_stacks(region)
            lambda_edge_retry_stacks.extend(retry_stacks)

        if not args.lambda_edge_retry or args.include_lambda_edge_retry:
            # Look for regular old stacks
            stacks = find_feature_stacks(region, active_branches)
            old_stacks.extend(stacks)

    all_stacks = old_stacks + lambda_edge_retry_stacks

    if not all_stacks:
        if args.lambda_edge_retry:
            console.print("[green]✓[/green] No Lambda@Edge blocked stacks ready for retry")
        else:
            console.print("[green]✓[/green] No old feature branch stacks found")
        return 0

    # Display stacks to be deleted
    table_title = "Stacks to Delete"
    if args.lambda_edge_retry:
        table_title = "Lambda@Edge Blocked Stacks Ready for Retry"
    elif args.include_lambda_edge_retry:
        table_title = "Old Stacks + Lambda@Edge Retries"

    table = Table(title=table_title)
    table.add_column("Stack Name")
    table.add_column("Region")
    table.add_column("Age/Status")
    table.add_column("Type")

    for stack in all_stacks:
        if stack.get("status") == "LAMBDA_EDGE_RETRY_READY":
            age_str = f"Failed {(datetime.now() - stack['failure_time']).days}d ago"
            stack_type = "Lambda@Edge Retry"
        else:
            age_days = (datetime.now() - stack["creation_time"]).days
            age_str = f"{age_days} days"
            stack_type = "Old Stack"
        table.add_row(stack["name"], stack["region"], age_str, stack_type)

    console.print(table)

    # Confirm deletion
    if not console.input("Delete these stacks? (y/N): ").lower().startswith("y"):
        console.print("Cancelled")
        return 0

    # Delete stacks
    for stack in all_stacks:
        delete_stack(stack["name"], stack["region"])

    return 0


def get_active_git_branches() -> list[str]:
    """Get list of active git branches."""
    try:
        # Get remote branches
        result = subprocess.run(["git", "branch", "-r"], capture_output=True, text=True, check=True)

        branches = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line and not line.startswith("origin/HEAD"):
                branch = line.replace("origin/", "")
                branches.append(branch)

        return branches
    except subprocess.CalledProcessError:
        console.print("[yellow]Warning: Could not get git branches[/yellow]")
        return []


def find_feature_stacks(region: str, active_branches: list[str]) -> list[dict]:
    """Find old feature branch stacks in a region."""
    cf_client = boto3.client("cloudformation", region_name=region)

    try:
        response = cf_client.list_stacks(
            StackStatusFilter=["CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"]
        )

        old_stacks = []
        cutoff_date = datetime.now() - timedelta(days=7)  # Consider stacks older than 7 days

        for stack in response["StackSummaries"]:
            stack_name = stack["StackName"]

            # Check if it's a feature branch stack
            if not stack_name.startswith("sflt-"):
                continue

            # Skip main/develop stacks
            if "sflt-main" in stack_name or "sflt-develop" in stack_name:
                continue

            # Skip the original stacks (no branch prefix)
            if stack_name in ["SfltAuthStack", "SfltStaticSiteStack"]:
                continue

            # Extract branch name from stack name
            branch_from_stack = extract_branch_from_stack_name(stack_name)

            # Check if branch is still active
            if branch_from_stack in active_branches:
                continue

            # Check if stack is old enough
            if stack["CreationTime"].replace(tzinfo=None) > cutoff_date:
                continue

            old_stacks.append(
                {
                    "name": stack_name,
                    "region": region,
                    "creation_time": stack["CreationTime"].replace(tzinfo=None),
                    "status": stack["StackStatus"],
                }
            )

        return old_stacks

    except Exception as e:
        console.print(f"[red]Error finding stacks in {region}: {e}[/red]")
        return []


def extract_branch_from_stack_name(stack_name: str) -> str:
    """Extract branch name from stack name."""
    # Remove 'sflt-' prefix and stack suffix
    if stack_name.startswith("sflt-"):
        branch_part = stack_name[5:]  # Remove 'sflt-'

        # Remove common suffixes
        if branch_part.endswith("-auth"):
            branch_part = branch_part[:-5]
        elif branch_part.endswith("-site"):
            branch_part = branch_part[:-5]

        # Convert back to branch format
        return branch_part.replace("-", "/")


def delete_stack(stack_name: str, region: str):
    """Delete a CloudFormation stack."""
    console.print(f"Deleting {stack_name} in {region}...")

    cf_client = boto3.client("cloudformation", region_name=region)

    try:
        cf_client.delete_stack(StackName=stack_name)
        console.print(f"[green]✓[/green] Started deletion of {stack_name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to delete {stack_name}: {e}")


def find_lambda_edge_retry_stacks(region: str) -> list[dict]:
    """Find DELETE_FAILED stacks that might be ready for Lambda@Edge retry."""
    cf_client = boto3.client("cloudformation", region_name=region)

    try:
        response = cf_client.list_stacks(StackStatusFilter=["DELETE_FAILED"])

        retry_stacks = []
        for stack in response["StackSummaries"]:
            stack_name = stack["StackName"]

            if not stack_name.startswith("sflt-"):
                continue

            # Check if failure was due to Lambda@Edge
            if is_lambda_edge_failure(cf_client, stack_name):
                # Check if enough time has passed (24h minimum)
                last_updated = stack["LastUpdatedTime"].replace(tzinfo=None)
                if last_updated < datetime.now() - timedelta(hours=24):
                    retry_stacks.append(
                        {
                            "name": stack_name,
                            "region": region,
                            "status": "LAMBDA_EDGE_RETRY_READY",
                            "failure_time": last_updated,
                        }
                    )

        return retry_stacks

    except Exception as e:
        console.print(f"[red]Error finding retry stacks in {region}: {e}[/red]")
        return []


def is_lambda_edge_failure(cf_client, stack_name: str) -> bool:
    """Check if stack failure was due to Lambda@Edge replication."""
    try:
        events = cf_client.describe_stack_events(StackName=stack_name)

        for event in events["StackEvents"]:
            if event.get("ResourceStatus") == "DELETE_FAILED":
                reason = event.get("ResourceStatusReason", "")
                if "replicated function" in reason.lower():
                    return True

    except Exception:
        pass

    return False


def list_blocked_stacks():
    """List Lambda@Edge blocked stacks only."""
    console.rule("[bold yellow]Lambda@Edge Blocked Stacks[/bold yellow]")

    regions = ["ap-southeast-2", "us-east-1"]
    blocked_stacks = []

    for region in regions:
        stacks = find_lambda_edge_retry_stacks(region)
        blocked_stacks.extend(stacks)

    if not blocked_stacks:
        console.print("[green]✓[/green] No Lambda@Edge blocked stacks found")
        return

    table = Table(title="Lambda@Edge Blocked Stacks")
    table.add_column("Stack Name")
    table.add_column("Region")
    table.add_column("Failed")
    table.add_column("Ready for Retry")

    for stack in blocked_stacks:
        failed_days = (datetime.now() - stack["failure_time"]).days
        hours_since = (datetime.now() - stack["failure_time"]).total_seconds() / 3600

        if hours_since >= 48:
            ready_status = "[green]Yes (48h+ elapsed)[/green]"
        elif hours_since >= 24:
            ready_status = "[yellow]Maybe (24h+ elapsed)[/yellow]"
        else:
            remaining_hours = int(24 - hours_since)
            ready_status = f"[red]No ({remaining_hours}h remaining)[/red]"

        table.add_row(stack["name"], stack["region"], f"{failed_days} days ago", ready_status)

    console.print(table)
    console.print()
    console.print("[cyan]💡 Lambda@Edge functions need 24-48h for global replication cleanup[/cyan]")
    console.print("[cyan]🚀 Use --lambda-edge-retry to attempt cleanup of ready stacks[/cyan]")


if __name__ == "__main__":
    sys.exit(main())
