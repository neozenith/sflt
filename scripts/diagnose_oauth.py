#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "python-dotenv",
#   "rich",
# ]
# ///
"""Diagnose OAuth configuration issues between Google, Cognito, and CloudFront."""

import logging
import os
import subprocess
import sys
import time
from typing import Any

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

# Load environment variables
load_dotenv()

console = Console()
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)


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


def get_cognito_config_from_stack() -> tuple[str, str]:
    """Get Cognito IDs from CloudFormation stack outputs."""
    console.rule("[bold blue]Getting Configuration from CloudFormation[/bold blue]")

    # Get from AuthStack
    auth_outputs = get_stack_outputs("SfltAuthStack", "ap-southeast-2")

    user_pool_id = auth_outputs.get("UserPoolId")
    client_id = auth_outputs.get("UserPoolClientId")

    if not user_pool_id or not client_id:
        console.print("[red]Could not find UserPoolId or UserPoolClientId in stack outputs[/red]")
        console.print("[yellow]Please ensure the stack is deployed and outputs are configured[/yellow]")
        return None, None

    console.print(f"[green]✓[/green] Found User Pool ID: [cyan]{user_pool_id}[/cyan]")
    console.print(f"[green]✓[/green] Found Client ID: [cyan]{client_id}[/cyan]")

    return user_pool_id, client_id


def check_stack_drift(stack_name: str, region: str):
    """Check if stack has drifted from template."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)

        # Initiate drift detection
        console.print(f"  Checking drift for [yellow]{stack_name}[/yellow]: [dim]Initiating...[/dim]")
        response = cf_client.detect_stack_drift(StackName=stack_name)
        drift_id = response["StackDriftDetectionId"]

        # Wait for drift detection to complete
        status = "DETECTION_IN_PROGRESS"
        for _ in range(30):  # Wait up to 30 seconds
            response = cf_client.describe_stack_drift_detection_status(StackDriftDetectionId=drift_id)
            status = response["DetectionStatus"]
            if status in ["DETECTION_COMPLETE", "DETECTION_FAILED"]:
                break
            time.sleep(1)

        if status == "DETECTION_COMPLETE":
            drift_status = response["StackDriftStatus"]
            if drift_status == "IN_SYNC":
                console.print(f"[green]✓[/green] [yellow]{stack_name}[/yellow] is [green]IN SYNC[/green] with template")
            else:
                console.print(
                    f"[yellow]{stack_name}[/yellow] has [red]DRIFTED[/red] from template: "
                    f"[yellow]{drift_status}[/yellow]"
                )
                if response.get("DriftedStackResourceCount", 0) > 0:
                    console.print(f"  [yellow]Drifted resources: {response['DriftedStackResourceCount']}[/yellow]")
        else:
            logger.error(f"Drift detection failed for {stack_name}")

    except Exception as e:
        logger.warning(f"Could not check drift for {stack_name}: {e}")


def get_cognito_config(user_pool_id: str, client_id: str) -> dict[str, Any]:
    """Get Cognito configuration from AWS."""
    client = boto3.client("cognito-idp", region_name="ap-southeast-2")

    try:
        response = client.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)
        return response["UserPoolClient"]
    except Exception as e:
        logger.error(f"Failed to get Cognito config: {e}")
        return {}


def get_google_project_info() -> dict[str, Any]:
    """Get Google Cloud project information."""
    result = {}

    # Get project ID from environment first
    result["project_id"] = os.getenv("GOOGLE_PROJECT_ID", "")

    # Try to get from gcloud if not in env
    if not result["project_id"]:
        try:
            project_id = subprocess.run(
                ["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=True
            ).stdout.strip()
            result["project_id"] = project_id
        except Exception:
            result["project_id"] = "Not set"

    # Get authenticated account
    try:
        account = subprocess.run(
            ["gcloud", "config", "get-value", "account"], capture_output=True, text=True, check=True
        ).stdout.strip()
        result["account"] = account
    except Exception:
        result["account"] = "Not authenticated"

    # Get OAuth client ID from env
    result["oauth_client_id"] = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "Not set")

    return result


def diagnose_cognito_settings(cognito_config: dict[str, Any]):
    """Diagnose Cognito OAuth settings."""
    console.rule("[bold blue]Cognito OAuth Configuration[/bold blue]")

    # Check OAuth flows
    allowed_flows = cognito_config.get("AllowedOAuthFlows", [])
    if "code" in allowed_flows:
        console.print("[green]✓[/green] Authorization code flow enabled")
    else:
        console.print("[red]✗[/red] Authorization code flow NOT enabled")

    # Check OAuth scopes
    scopes = cognito_config.get("AllowedOAuthScopes", [])
    required_scopes = ["openid", "email", "profile"]
    for scope in required_scopes:
        if scope in scopes:
            console.print(f"[green]✓[/green] Scope '[cyan]{scope}[/cyan]' enabled")
        else:
            console.print(f"[red]✗[/red] Scope '[cyan]{scope}[/cyan]' NOT enabled")

    # Check supported identity providers
    providers = cognito_config.get("SupportedIdentityProviders", [])
    if "Google" in providers:
        console.print("[green]✓[/green] [blue]Google[/blue] identity provider enabled")
    else:
        console.print("[red]✗[/red] [blue]Google[/blue] identity provider NOT enabled")

    # Check callback URLs
    console.print("\n[bold]Callback URLs:[/bold]")
    for url in cognito_config.get("CallbackURLs", []):
        console.print(f"    [dim]-[/dim] [link]{url}[/link]")

    # Check PKCE - THIS IS CRITICAL!
    console.print("\n[bold red]PKCE Configuration (CRITICAL):[/bold red]")
    if cognito_config.get("AllowedOAuthFlowsUserPoolClient"):
        # Check if PKCE is required
        generate_secret = cognito_config.get("GenerateSecret", False)

        if generate_secret:
            console.print("[red]✗[/red] Client has a secret ([red]not compatible with SPA/PKCE[/red])")
            console.print("[yellow]SPAs cannot use client secrets - PKCE should be used instead[/yellow]")
        else:
            console.print("[green]✓[/green] No client secret ([green]compatible with PKCE[/green])")

        # Check for PKCE requirement
        # Note: AWS doesn't expose PKCE setting directly via API
        logger.warning("PKCE requirement cannot be checked via API")
        logger.info("  Check in AWS Console: Cognito > User Pool > App Integration > App Client")
        logger.info("  Required for SPA: Enable 'Authorization code grant' with PKCE")

        # Check explicit auth flows for PKCE support
        explicit_flows = cognito_config.get("ExplicitAuthFlows", [])
        if "ALLOW_REFRESH_TOKEN_AUTH" in explicit_flows:
            console.print("[green]✓[/green] Refresh token auth enabled")
    else:
        console.print("[red]✗[/red] OAuth flows not enabled for user pool client")

    # Check token validity
    console.print("\n[bold]Token Configuration:[/bold]")
    access_validity = cognito_config.get("AccessTokenValidity", 60)
    console.print(f"  [cyan]Access Token Validity:[/cyan] [yellow]{access_validity}[/yellow] minutes")
    id_validity = cognito_config.get("IdTokenValidity", 60)
    console.print(f"  [cyan]ID Token Validity:[/cyan] [yellow]{id_validity}[/yellow] minutes")
    refresh_validity = cognito_config.get("RefreshTokenValidity", 30)
    console.print(f"  [cyan]Refresh Token Validity:[/cyan] [yellow]{refresh_validity}[/yellow] days")


def check_cloudfront_domains() -> str | None:
    """Check CloudFront domain configuration."""
    console.rule("[bold blue]CloudFront Domains[/bold blue]")

    static_outputs = get_stack_outputs("SfltStaticSiteStack", "us-east-1")
    domain = static_outputs.get("DistributionDomainName")

    if domain:
        console.print(f"[green]✓[/green] CloudFront domain: [link]https://{domain}[/link]")
        return domain
    else:
        console.print("[red]✗[/red] Could not find CloudFront domain in stack outputs")
        return None


def diagnose_google_oauth(user_pool_domain: str):
    """Diagnose Google OAuth settings."""
    console.rule("[bold blue]Google OAuth Configuration[/bold blue]")

    google_info = get_google_project_info()

    console.print(f"  [cyan]Project ID:[/cyan] [yellow]{google_info['project_id']}[/yellow]")
    console.print(f"  [cyan]Account:[/cyan] [yellow]{google_info['account']}[/yellow]")
    console.print(f"  [cyan]OAuth Client ID:[/cyan] [yellow]{google_info['oauth_client_id']}[/yellow]")

    # Expected redirect URI for Cognito
    expected_uri = f"https://{user_pool_domain}.auth.ap-southeast-2.amazoncognito.com/oauth2/idpresponse"
    console.print(f"\n  [cyan]Expected Redirect URI:[/cyan] [link]{expected_uri}[/link]")

    logger.warning("\nPlease verify in Google Cloud Console:")
    logger.info(f"  1. Go to: https://console.cloud.google.com/apis/credentials?project={google_info['project_id']}")
    logger.info(f"  2. Click on OAuth 2.0 Client: {google_info['oauth_client_id']}")
    logger.info("  3. Verify Authorized redirect URIs includes:")
    logger.info(f"     - {expected_uri}")
    logger.info("  4. Verify Authorized JavaScript origins includes:")
    logger.info(f"     - https://{user_pool_domain}.auth.ap-southeast-2.amazoncognito.com")


def check_cognito_identity_provider(user_pool_id: str):
    """Check Cognito Google identity provider configuration."""
    console.rule("[bold blue]Cognito Google Identity Provider[/bold blue]")

    client = boto3.client("cognito-idp", region_name="ap-southeast-2")

    try:
        response = client.describe_identity_provider(UserPoolId=user_pool_id, ProviderName="Google")

        provider = response["IdentityProvider"]
        console.print(f"[green]✓[/green] Provider Type: [cyan]{provider['ProviderType']}[/cyan]")
        console.print(f"[green]✓[/green] Provider Name: [cyan]{provider['ProviderName']}[/cyan]")

        # Check attributes
        logger.info("\nAttribute Mapping:")
        for attr, value in provider.get("AttributeMapping", {}).items():
            logger.info(f"    {attr}: {value}")

        # Check provider details
        logger.info("\nProvider Details:")
        details = provider.get("ProviderDetails", {})
        if "client_id" in details:
            logger.info(f"    Google Client ID: {details['client_id']}")
            if details["client_id"] == os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
                logger.info("  ✓ Client ID matches .env file")
            else:
                logger.error("  Client ID does NOT match .env file!")

        if "authorize_scopes" in details:
            logger.info(f"    Authorize Scopes: {details['authorize_scopes']}")

    except Exception as e:
        logger.error(f"Failed to get identity provider: {e}")


def generate_test_urls(cloudfront_domain: str, client_id: str):
    """Generate test URLs for debugging."""
    console.rule("[bold blue]Test URLs[/bold blue]")

    logger.info("1. Direct Lambda@Edge test:")
    logger.info(f"   curl -I https://{cloudfront_domain}/admin")

    logger.info("\n2. OAuth flow test (with lowercase response_type):")
    oauth_url = (
        f"https://sflt-auth.auth.ap-southeast-2.amazoncognito.com/oauth2/authorize?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"scope=openid+email+profile&"
        f"redirect_uri=https%3A%2F%2F{cloudfront_domain}%2F&"
        f"state=%7B%22target%22%3A%20%22%2Fadmin%22%7D"
    )
    logger.info(f"   curl -I '{oauth_url}'")

    logger.info("\n3. Direct Google provider test:")
    google_url = (
        f"https://sflt-auth.auth.ap-southeast-2.amazoncognito.com/oauth2/authorize?"
        f"identity_provider=Google&"
        f"redirect_uri=https://{cloudfront_domain}/&"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"state=%7B%22target%22%3A%20%22%2Fadmin%22%7D&"
        f"scope=openid+email+profile"
    )
    logger.info(f"   curl -I '{google_url}'")


def main():
    """Run all diagnostics."""
    console.print("\n[bold magenta]OAuth Configuration Diagnostic Tool[/bold magenta]")
    console.print("[dim]Checking Google, Cognito, and CloudFront settings...[/dim]\n")

    # Check drift first
    console.rule("[bold blue]Stack Drift Detection[/bold blue]")
    check_stack_drift("SfltAuthStack", "ap-southeast-2")
    check_stack_drift("SfltStaticSiteStack", "us-east-1")

    # Get IDs from CloudFormation
    user_pool_id, client_id = get_cognito_config_from_stack()
    if not user_pool_id or not client_id:
        console.print("[red]✗[/red] Cannot continue without User Pool ID and Client ID")
        return 1

    # Get user pool domain from outputs
    auth_outputs = get_stack_outputs("SfltAuthStack", "ap-southeast-2")
    user_pool_domain = auth_outputs.get("UserPoolDomainName", "sflt-auth")

    # Get configurations
    cognito_config = get_cognito_config(user_pool_id, client_id)

    # Run diagnostics
    diagnose_cognito_settings(cognito_config)
    cloudfront_domain = check_cloudfront_domains()
    diagnose_google_oauth(user_pool_domain)
    check_cognito_identity_provider(user_pool_id)

    if cloudfront_domain:
        generate_test_urls(cloudfront_domain, client_id)

    # Final recommendations
    console.rule("[bold red]Critical Checklist[/bold red]")

    if not cognito_config.get("GenerateSecret", False):
        console.print("[green]✓[/green] Client has no secret ([green]correct for SPA[/green])")
    else:
        console.print("[red]✗[/red] Client has a secret - [red]incompatible with SPA/PKCE[/red]")

    console.print("\n[bold yellow]MANUAL CHECKS REQUIRED:[/bold yellow]")
    console.print("[bold]1.[/bold] [cyan]AWS Console:[/cyan] Check if PKCE is enabled for the App Client")
    console.print("   [dim]-[/dim] Go to Cognito > User Pools > App Integration > App Client")
    console.print("   [dim]-[/dim] Ensure 'Authorization code grant' is selected [red]WITH PKCE required[/red]")
    console.print("\n[bold]2.[/bold] [cyan]Google Console:[/cyan] Verify redirect URIs are correctly set")
    console.print("   [dim]-[/dim] Must include Cognito's /oauth2/idpresponse endpoint")
    console.print("\n[bold]3.[/bold] [cyan]Test the full OAuth flow in a browser[/cyan]")
    console.print("   [dim]-[/dim] Clear cookies first to ensure clean test")

    return 0


if __name__ == "__main__":
    sys.exit(main())
