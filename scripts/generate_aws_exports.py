#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
#   "jinja2",
# ]
# ///
"""Generate aws-exports.js from CDK stack outputs."""

import logging
import sys
from pathlib import Path
from typing import Any

import boto3
from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Configure Rich logging
from rich.console import Console
from rich.logging import RichHandler

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cdk.config import get_deployment_config

console = Console()
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)

# Constants
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def get_stack_outputs(stack_name: str, region: str) -> dict[str, str]:
    """Get CloudFormation stack outputs."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)
        response = cf_client.describe_stacks(StackName=stack_name)

        outputs = {}
        for output in response["Stacks"][0]["Outputs"]:
            outputs[output["OutputKey"]] = output["OutputValue"]

        return outputs
    except Exception as e:
        logger.error(f"Failed to get stack outputs for {stack_name}: {e}")
        return {}


def generate_aws_exports_content(auth_outputs: dict[str, str], static_outputs: dict[str, str]) -> str:
    """Generate the content for aws-exports.js file using Jinja2 templating."""

    # Template is co-located with the output file in frontend/src
    template_dir = FRONTEND_DIR / "src"

    # Set up Jinja2 environment with StrictUndefined for fail-fast on missing variables
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )

    # Get template
    template = env.get_template("aws-exports.js.template")

    # Prepare template variables
    user_pool_id = auth_outputs.get("UserPoolId", "")
    user_pool_client_id = auth_outputs.get("UserPoolClientId", "")
    identity_pool_id = auth_outputs.get("IdentityPoolId", "")
    user_pool_domain = auth_outputs.get("UserPoolDomainName", "")
    cloudfront_domain = static_outputs.get("DistributionDomainName", "")

    # Build redirect URLs
    redirect_urls = ["http://localhost:5173/"]
    if cloudfront_domain:
        redirect_urls.append(f"https://{cloudfront_domain}/")

    template_vars = {
        "user_pool_id": user_pool_id,
        "user_pool_client_id": user_pool_client_id,
        "identity_pool_id": identity_pool_id,
        "user_pool_domain": user_pool_domain,
        "redirect_urls": redirect_urls,
    }

    # Render template
    return template.render(**template_vars)


def read_existing_config(file_path: Path) -> dict[str, Any]:
    """Read existing aws-exports.js and extract configuration."""
    if not file_path.exists():
        return {}

    try:
        content = file_path.read_text()
        # Extract values using simple string parsing
        config = {}

        if "userPoolId: '" in content:
            start = content.find("userPoolId: '") + len("userPoolId: '")
            end = content.find("'", start)
            config["userPoolId"] = content[start:end]

        if "userPoolClientId: '" in content:
            start = content.find("userPoolClientId: '") + len("userPoolClientId: '")
            end = content.find("'", start)
            config["userPoolClientId"] = content[start:end]

        if "redirectSignIn: [" in content:
            start = content.find("redirectSignIn: [") + len("redirectSignIn: [")
            end = content.find("]", start)
            redirect_str = content[start:end]
            # Extract CloudFront domain if present
            if "cloudfront.net" in redirect_str:
                cf_start = redirect_str.find("https://") + len("https://")
                cf_end = redirect_str.find(".cloudfront.net") + len(".cloudfront.net")
                config["cloudfrontDomain"] = redirect_str[cf_start:cf_end]

        return config

    except Exception as e:
        logger.warning(f"Could not parse existing config: {e}")
        return {}


def check_config_drift(
    existing_config: dict[str, Any], auth_outputs: dict[str, str], static_outputs: dict[str, str]
) -> bool:
    """Check if the configuration has drifted from stack outputs."""
    drifted = False

    # Check User Pool ID
    if existing_config.get("userPoolId") != auth_outputs.get("UserPoolId"):
        old_id = existing_config.get("userPoolId")
        new_id = auth_outputs.get("UserPoolId")
        console.print(f"[yellow]User Pool ID drift:[/yellow] [red]{old_id}[/red] → [green]{new_id}[/green]")
        drifted = True

    # Check User Pool Client ID
    if existing_config.get("userPoolClientId") != auth_outputs.get("UserPoolClientId"):
        old_client = existing_config.get("userPoolClientId")
        new_client = auth_outputs.get("UserPoolClientId")
        console.print(f"[yellow]Client ID drift:[/yellow] [red]{old_client}[/red] → [green]{new_client}[/green]")
        drifted = True

    # Check CloudFront domain
    current_cf = existing_config.get("cloudfrontDomain", "").replace("https://", "").replace("/", "")
    new_cf = static_outputs.get("DistributionDomainName", "")
    if current_cf != new_cf:
        console.print(f"[yellow]CloudFront domain drift:[/yellow] [red]{current_cf}[/red] → [green]{new_cf}[/green]")
        drifted = True

    return drifted


def generate_aws_exports(verbose: bool = True) -> bool:
    """Generate aws-exports.js from CDK outputs.

    Args:
        verbose: Whether to print detailed output

    Returns:
        True if successful, False otherwise
    """
    # Get deployment configuration
    config = get_deployment_config()

    # Get stack outputs - use shared util if available
    try:
        from orchestration_utils import get_stack_outputs as get_stack_outputs_cached

        auth_outputs = get_stack_outputs_cached(config.auth_stack_name, config.auth_region)
        if auth_outputs:
            auth_outputs = auth_outputs.get("Outputs", {})

        static_outputs = get_stack_outputs_cached(config.static_site_stack_name, config.site_region)
        if static_outputs:
            static_outputs = static_outputs.get("Outputs", {})
    except ImportError:
        # Fallback to local function
        auth_outputs = get_stack_outputs(config.auth_stack_name, config.auth_region)
        static_outputs = get_stack_outputs(config.static_site_stack_name, config.site_region)

    if not auth_outputs or not static_outputs:
        return False

    # Validate required outputs
    required_auth_outputs = ["UserPoolId", "UserPoolClientId", "IdentityPoolId", "UserPoolDomainName"]
    missing_outputs = [key for key in required_auth_outputs if key not in auth_outputs]

    if missing_outputs:
        if verbose:
            missing_str = ", ".join(missing_outputs)
            console.print(f"[red]✗[/red] Missing required Auth Stack outputs: [yellow]{missing_str}[/yellow]")
        return False

    # Path to aws-exports.js
    aws_exports_path = FRONTEND_DIR / "src" / "aws-exports.js"

    # Check for existing config and drift
    existing_config = read_existing_config(aws_exports_path)
    if existing_config and verbose:
        check_config_drift(existing_config, auth_outputs, static_outputs)

    # Generate new content
    content = generate_aws_exports_content(auth_outputs, static_outputs)

    # Write to file
    try:
        aws_exports_path.write_text(content)

        if verbose:
            console.print(f"[green]✓[/green] Generated: [cyan]{aws_exports_path}[/cyan]")
            console.print(f"  [cyan]User Pool ID:[/cyan] [yellow]{auth_outputs['UserPoolId']}[/yellow]")
            console.print(f"  [cyan]Client ID:[/cyan] [yellow]{auth_outputs['UserPoolClientId']}[/yellow]")
            cf_domain = static_outputs.get("DistributionDomainName", "N/A")
            console.print(f"  [cyan]CloudFront:[/cyan] [link]https://{cf_domain}/[/link]")

        return True

    except Exception as e:
        if verbose:
            console.print(f"[red]✗[/red] Failed to write aws-exports.js: [red]{e}[/red]")
        return False


def main():
    """Main function to generate aws-exports.js from CDK outputs."""
    console.rule("[bold magenta]AWS Exports Configuration Generator[/bold magenta]")

    # Get deployment configuration
    config = get_deployment_config()

    console.print(f"\n[dim]Environment: [cyan]{config.environment}[/cyan][/dim]")
    console.print(f"[dim]Branch: [cyan]{config.branch}[/cyan][/dim]")
    console.print(f"[dim]Auth Stack: [yellow]{config.auth_stack_name}[/yellow][/dim]")
    console.print(f"[dim]Site Stack: [yellow]{config.static_site_stack_name}[/yellow][/dim]")

    console.print("\n[dim]Fetching stack outputs and generating configuration...[/dim]")

    success = generate_aws_exports(verbose=True)

    if success:
        console.print("\n[green]✅[/green] Configuration generated successfully")
        return 0
    else:
        console.print("\n[red]✗[/red] Configuration generation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
