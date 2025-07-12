#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "python-dotenv",
# ]
# ///
"""Diagnose OAuth configuration issues between Google, Cognito, and CloudFront."""

import os
import subprocess
from typing import Any

import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(key: str, value: str):
    print(f"  {Colors.BOLD}{key}:{Colors.ENDC} {value}")


def get_stack_outputs(stack_name: str, region: str) -> dict[str, str]:
    """Get CloudFormation stack outputs."""
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        response = cf_client.describe_stacks(StackName=stack_name)
        
        outputs = {}
        for output in response['Stacks'][0]['Outputs']:
            outputs[output['OutputKey']] = output['OutputValue']
        
        return outputs
    except Exception as e:
        print_error(f"Failed to get stack outputs for {stack_name}: {e}")
        return {}


def get_cognito_config_from_stack() -> tuple[str, str]:
    """Get Cognito IDs from CloudFormation stack outputs."""
    print_header("Getting Configuration from CloudFormation")
    
    # Get from AuthStack
    auth_outputs = get_stack_outputs('SfltAuthStack', 'ap-southeast-2')
    
    user_pool_id = auth_outputs.get('UserPoolId')
    client_id = auth_outputs.get('UserPoolClientId')
    
    if not user_pool_id or not client_id:
        print_error("Could not find UserPoolId or UserPoolClientId in stack outputs")
        print_warning("Please ensure the stack is deployed and outputs are configured")
        return None, None
    
    print_success(f"Found User Pool ID: {user_pool_id}")
    print_success(f"Found Client ID: {client_id}")
    
    return user_pool_id, client_id


def check_stack_drift(stack_name: str, region: str):
    """Check if stack has drifted from template."""
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        
        # Initiate drift detection
        print_info(f"Checking drift for {stack_name}", "Initiating...")
        response = cf_client.detect_stack_drift(StackName=stack_name)
        drift_id = response['StackDriftDetectionId']
        
        # Wait for drift detection to complete
        import time
        for _ in range(30):  # Wait up to 30 seconds
            response = cf_client.describe_stack_drift_detection_status(
                StackDriftDetectionId=drift_id
            )
            status = response['DetectionStatus']
            if status in ['DETECTION_COMPLETE', 'DETECTION_FAILED']:
                break
            time.sleep(1)
        
        if status == 'DETECTION_COMPLETE':
            drift_status = response['StackDriftStatus']
            if drift_status == 'IN_SYNC':
                print_success(f"{stack_name} is IN SYNC with template")
            else:
                print_warning(f"{stack_name} has DRIFTED from template: {drift_status}")
                if response.get('DriftedStackResourceCount', 0) > 0:
                    print_warning(f"  Drifted resources: {response['DriftedStackResourceCount']}")
        else:
            print_error(f"Drift detection failed for {stack_name}")
            
    except Exception as e:
        print_warning(f"Could not check drift for {stack_name}: {e}")


def get_cognito_config(user_pool_id: str, client_id: str) -> dict[str, Any]:
    """Get Cognito configuration from AWS."""
    client = boto3.client('cognito-idp', region_name='ap-southeast-2')
    
    try:
        response = client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id
        )
        return response['UserPoolClient']
    except Exception as e:
        print_error(f"Failed to get Cognito config: {e}")
        return {}


def get_google_project_info() -> dict[str, Any]:
    """Get Google Cloud project information."""
    result = {}
    
    # Get project ID from environment first
    result['project_id'] = os.getenv('GOOGLE_PROJECT_ID', '')
    
    # Try to get from gcloud if not in env
    if not result['project_id']:
        try:
            project_id = subprocess.run(
                ['gcloud', 'config', 'get-value', 'project'],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            result['project_id'] = project_id
        except Exception:
            result['project_id'] = 'Not set'
    
    # Get authenticated account
    try:
        account = subprocess.run(
            ['gcloud', 'config', 'get-value', 'account'],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        result['account'] = account
    except Exception:
        result['account'] = 'Not authenticated'
    
    # Get OAuth client ID from env
    result['oauth_client_id'] = os.getenv('GOOGLE_OAUTH_CLIENT_ID', 'Not set')
    
    return result


def diagnose_cognito_settings(cognito_config: dict[str, Any]):
    """Diagnose Cognito OAuth settings."""
    print_header("Cognito OAuth Configuration")
    
    # Check OAuth flows
    allowed_flows = cognito_config.get('AllowedOAuthFlows', [])
    if 'code' in allowed_flows:
        print_success("Authorization code flow enabled")
    else:
        print_error("Authorization code flow NOT enabled")
    
    # Check OAuth scopes
    scopes = cognito_config.get('AllowedOAuthScopes', [])
    required_scopes = ['openid', 'email', 'profile']
    for scope in required_scopes:
        if scope in scopes:
            print_success(f"Scope '{scope}' enabled")
        else:
            print_error(f"Scope '{scope}' NOT enabled")
    
    # Check supported identity providers
    providers = cognito_config.get('SupportedIdentityProviders', [])
    if 'Google' in providers:
        print_success("Google identity provider enabled")
    else:
        print_error("Google identity provider NOT enabled")
    
    # Check callback URLs
    print_info("\nCallback URLs", "")
    for url in cognito_config.get('CallbackURLs', []):
        print(f"    - {url}")
    
    # Check PKCE - THIS IS CRITICAL!
    print("\n" + Colors.BOLD + "PKCE Configuration:" + Colors.ENDC)
    if cognito_config.get('AllowedOAuthFlowsUserPoolClient'):
        # Check if PKCE is required
        generate_secret = cognito_config.get('GenerateSecret', False)
        
        if generate_secret:
            print_error("Client has a secret (not compatible with SPA/PKCE)")
            print_warning("SPAs cannot use client secrets - PKCE should be used instead")
        else:
            print_success("No client secret (compatible with PKCE)")
        
        # Check for PKCE requirement
        # Note: AWS doesn't expose PKCE setting directly via API
        print_warning("PKCE requirement cannot be checked via API")
        print_info("Check in AWS Console", "Cognito > User Pool > App Integration > App Client")
        print_info("Required for SPA", "Enable 'Authorization code grant' with PKCE")
        
        # Check explicit auth flows for PKCE support
        explicit_flows = cognito_config.get('ExplicitAuthFlows', [])
        if 'ALLOW_REFRESH_TOKEN_AUTH' in explicit_flows:
            print_success("Refresh token auth enabled")
    else:
        print_error("OAuth flows not enabled for user pool client")
    
    # Check token validity
    print("\n" + Colors.BOLD + "Token Configuration:" + Colors.ENDC)
    print_info("Access Token Validity", f"{cognito_config.get('AccessTokenValidity', 60)} minutes")
    print_info("ID Token Validity", f"{cognito_config.get('IdTokenValidity', 60)} minutes")
    print_info("Refresh Token Validity", f"{cognito_config.get('RefreshTokenValidity', 30)} days")


def check_cloudfront_domains() -> str:
    """Check CloudFront domain configuration."""
    print_header("CloudFront Domains")
    
    static_outputs = get_stack_outputs('SfltStaticSiteStack', 'us-east-1')
    domain = static_outputs.get('DistributionDomainName')
    
    if domain:
        print_success(f"CloudFront domain: https://{domain}")
        return domain
    else:
        print_error("Could not find CloudFront domain in stack outputs")
        return None


def diagnose_google_oauth(user_pool_domain: str):
    """Diagnose Google OAuth settings."""
    print_header("Google OAuth Configuration")
    
    google_info = get_google_project_info()
    
    print_info("Project ID", google_info['project_id'])
    print_info("Account", google_info['account'])
    print_info("OAuth Client ID", google_info['oauth_client_id'])
    
    # Expected redirect URI for Cognito
    expected_uri = f"https://{user_pool_domain}.auth.ap-southeast-2.amazoncognito.com/oauth2/idpresponse"
    print_info("\nExpected Redirect URI", expected_uri)
    
    print_warning("\nPlease verify in Google Cloud Console:")
    print(f"  1. Go to: https://console.cloud.google.com/apis/credentials?project={google_info['project_id']}")
    print(f"  2. Click on OAuth 2.0 Client: {google_info['oauth_client_id']}")
    print("  3. Verify Authorized redirect URIs includes:")
    print(f"     - {expected_uri}")
    print("  4. Verify Authorized JavaScript origins includes:")
    print(f"     - https://{user_pool_domain}.auth.ap-southeast-2.amazoncognito.com")


def check_cognito_identity_provider(user_pool_id: str):
    """Check Cognito Google identity provider configuration."""
    print_header("Cognito Google Identity Provider")
    
    client = boto3.client('cognito-idp', region_name='ap-southeast-2')
    
    try:
        response = client.describe_identity_provider(
            UserPoolId=user_pool_id,
            ProviderName='Google'
        )
        
        provider = response['IdentityProvider']
        print_success(f"Provider Type: {provider['ProviderType']}")
        print_success(f"Provider Name: {provider['ProviderName']}")
        
        # Check attributes
        print("\nAttribute Mapping:")
        for attr, value in provider.get('AttributeMapping', {}).items():
            print_info(f"  {attr}", value)
        
        # Check provider details
        print("\nProvider Details:")
        details = provider.get('ProviderDetails', {})
        if 'client_id' in details:
            print_info("  Google Client ID", details['client_id'])
            if details['client_id'] == os.getenv('GOOGLE_OAUTH_CLIENT_ID'):
                print_success("  Client ID matches .env file")
            else:
                print_error("  Client ID does NOT match .env file!")
        
        if 'authorize_scopes' in details:
            print_info("  Authorize Scopes", details['authorize_scopes'])
            
    except Exception as e:
        print_error(f"Failed to get identity provider: {e}")


def generate_test_urls(cloudfront_domain: str, client_id: str):
    """Generate test URLs for debugging."""
    print_header("Test URLs")
    
    print("1. Direct Lambda@Edge test:")
    print(f"   curl -I https://{cloudfront_domain}/admin")
    
    print("\n2. OAuth flow test (with lowercase response_type):")
    oauth_url = (
        f"https://sflt-auth.auth.ap-southeast-2.amazoncognito.com/oauth2/authorize?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"scope=openid+email+profile&"
        f"redirect_uri=https%3A%2F%2F{cloudfront_domain}%2F&"
        f"state=%7B%22target%22%3A%20%22%2Fadmin%22%7D"
    )
    print(f"   curl -I '{oauth_url}'")
    
    print("\n3. Direct Google provider test:")
    google_url = (
        f"https://sflt-auth.auth.ap-southeast-2.amazoncognito.com/oauth2/authorize?"
        f"identity_provider=Google&"
        f"redirect_uri=https://{cloudfront_domain}/&"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"state=%7B%22target%22%3A%20%22%2Fadmin%22%7D&"
        f"scope=openid+email+profile"
    )
    print(f"   curl -I '{google_url}'")


def main():
    """Run all diagnostics."""
    print(Colors.BOLD + "\nOAuth Configuration Diagnostic Tool" + Colors.ENDC)
    print("Checking Google, Cognito, and CloudFront settings...\n")
    
    # Check drift first
    print_header("Stack Drift Detection")
    check_stack_drift('SfltAuthStack', 'ap-southeast-2')
    check_stack_drift('SfltStaticSiteStack', 'us-east-1')
    
    # Get IDs from CloudFormation
    user_pool_id, client_id = get_cognito_config_from_stack()
    if not user_pool_id or not client_id:
        print_error("Cannot continue without User Pool ID and Client ID")
        return
    
    # Get user pool domain from outputs
    auth_outputs = get_stack_outputs('SfltAuthStack', 'ap-southeast-2')
    user_pool_domain = auth_outputs.get('UserPoolDomainName', 'sflt-auth')
    
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
    print_header("Critical Checklist")
    
    if not cognito_config.get('GenerateSecret', False):
        print_success("✓ Client has no secret (correct for SPA)")
    else:
        print_error("✗ Client has a secret - incompatible with SPA/PKCE")
    
    print("\n" + Colors.YELLOW + "MANUAL CHECKS REQUIRED:" + Colors.ENDC)
    print("1. AWS Console: Check if PKCE is enabled for the App Client")
    print("   - Go to Cognito > User Pools > App Integration > App Client")
    print("   - Ensure 'Authorization code grant' is selected WITH PKCE required")
    print("\n2. Google Console: Verify redirect URIs are correctly set")
    print("   - Must include Cognito's /oauth2/idpresponse endpoint")
    print("\n3. Test the full OAuth flow in a browser")
    print("   - Clear cookies first to ensure clean test")


if __name__ == "__main__":
    main()