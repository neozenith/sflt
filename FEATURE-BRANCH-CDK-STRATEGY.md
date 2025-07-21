# Feature Branch CDK Deployment Strategy

## Current Infrastructure Analysis

### Current Stack Structure
```
SfltAuthStack (ap-southeast-2)
├── Cognito User Pool: "sflt-user-pool"
├── Cognito User Pool Client
├── Google OAuth Identity Provider
└── Secrets Manager: Google OAuth credentials

SfltStaticSiteStack (us-east-1)
├── Lambda@Edge: "SfltAuthLambdaEdgeV6"
├── S3 Bucket: <generated-name>
├── CloudFront Distribution
└── S3 Deployment
```

### Current Limitations for Feature Branch Deployment

**1. Hard-coded Resource Names**
```python
# In auth_stack.py
user_pool_name="sflt-user-pool"  # Fixed name conflicts between branches

# In static_site_stack.py  
function_name="SfltAuthLambdaEdgeV6"  # Fixed name conflicts
```

**2. Stack Name Conflicts**
```python
# In app.py
AuthStack(app, "SfltAuthStack", ...)        # Same across all branches
StaticSiteStack(app, "SfltStaticSiteStack", ...)  # Same across all branches
```

**3. Cross-Region Dependencies**
- Auth stack (ap-southeast-2) exports values
- Static site stack (us-east-1) imports values
- Branch isolation requires separate exports

**4. Configuration Generation Hardcoded to Specific Stacks**
```python
# In generate_aws_exports.py
auth_outputs = get_stack_outputs("SfltAuthStack", "ap-southeast-2")
static_outputs = get_stack_outputs("SfltStaticSiteStack", "us-east-1")
```

## Solution: Environment-Based Feature Branch Isolation

### Strategy Overview

**Approach**: Use environment-based naming with branch/environment prefixes to create completely isolated deployments.

**Benefits**:
- ✅ Complete resource isolation between branches
- ✅ Parallel development without conflicts
- ✅ Easy cleanup of feature branch resources
- ✅ Maintains cross-region functionality
- ✅ Preserves existing deployment patterns

### Implementation Design

#### 1. Environment Configuration System

**New File: `cdk/config.py`**
```python
#!/usr/bin/env python3
"""Environment configuration for feature branch deployments."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeploymentConfig:
    """Configuration for a deployment environment."""
    environment: str  # dev, staging, prod, feature-branch-name
    branch: str      # git branch name
    aws_profile: str # AWS profile to use
    account: str     # AWS account ID
    auth_region: str # Region for auth stack
    site_region: str # Region for static site (must be us-east-1 for Lambda@Edge)
    
    @property
    def stack_prefix(self) -> str:
        """Generate stack prefix for this environment."""
        # Sanitize branch name for AWS resources
        sanitized = self.branch.replace('/', '-').replace('_', '-').lower()
        return f"sflt-{sanitized}"
    
    @property
    def resource_prefix(self) -> str:
        """Generate resource prefix for this environment."""
        return self.stack_prefix
    
    @property
    def auth_stack_name(self) -> str:
        return f"{self.stack_prefix}-auth"
    
    @property
    def static_site_stack_name(self) -> str:
        return f"{self.stack_prefix}-site"


def get_deployment_config() -> DeploymentConfig:
    """Get deployment configuration from environment variables."""
    
    # Determine environment and branch
    branch = os.getenv("GIT_BRANCH") or get_git_branch()
    environment = determine_environment(branch)
    
    return DeploymentConfig(
        environment=environment,
        branch=branch,
        aws_profile=os.getenv("AWS_PROFILE", "sflt"),
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        auth_region=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"),
        site_region="us-east-1"  # Required for Lambda@Edge
    )


def get_git_branch() -> str:
    """Get current git branch name."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def determine_environment(branch: str) -> str:
    """Determine environment type from branch name."""
    if branch == "main":
        return "prod"
    elif branch == "develop":
        return "staging"
    elif branch.startswith("feature/") or branch.startswith("fix/"):
        return "feature"
    else:
        return "dev"


def is_feature_branch() -> bool:
    """Check if current deployment is for a feature branch."""
    config = get_deployment_config()
    return config.environment == "feature"
```

#### 2. Enhanced CDK App Entry Point

**Updated `app.py`**
```python
#!/usr/bin/env python3
import os
import aws_cdk as cdk
from dotenv import load_dotenv

from cdk.config import get_deployment_config
from cdk.auth_stack import AuthStack
from cdk.static_site_stack import StaticSiteStack

# Load environment variables
load_dotenv()

# Get deployment configuration
config = get_deployment_config()

app = cdk.App()

# Add deployment context
app.node.set_context("deployment:config", {
    "environment": config.environment,
    "branch": config.branch,
    "stackPrefix": config.stack_prefix
})

print(f"🚀 Deploying {config.environment} environment for branch: {config.branch}")
print(f"📦 Stack prefix: {config.stack_prefix}")

# Authentication stack
auth_stack = AuthStack(
    app,
    config.auth_stack_name,
    config=config,
    env=cdk.Environment(
        account=config.account,
        region=config.auth_region,
    ),
    description=f"Authentication infrastructure for {config.branch} branch",
)

# Static site stack
static_site_stack = StaticSiteStack(
    app,
    config.static_site_stack_name,
    config=config,
    auth_stack=auth_stack,
    env=cdk.Environment(
        account=config.account,
        region=config.site_region,
    ),
    description=f"Static React website for {config.branch} branch",
)

# Add dependency
static_site_stack.add_dependency(auth_stack)

app.synth()
```

#### 3. Environment-Aware CDK Stacks

**Enhanced `cdk/auth_stack.py`**
```python
import os
from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    SecretValue,
    Stack,
    Tags,
)
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from .config import DeploymentConfig


class AuthStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        config: DeploymentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.config = config
        
        # Apply consistent tagging
        self._apply_tags()
        
        # Create environment-specific resources
        self._create_secrets()
        self._create_user_pool()
        self._create_outputs()
    
    def _apply_tags(self) -> None:
        """Apply consistent tags for resource management."""
        Tags.of(self).add("Environment", self.config.environment)
        Tags.of(self).add("Branch", self.config.branch)
        Tags.of(self).add("Project", "sflt")
        Tags.of(self).add("ManagedBy", "cdk")
        
        # Add feature branch specific tags for easy cleanup
        if self.config.environment == "feature":
            Tags.of(self).add("FeatureBranch", self.config.branch)
            Tags.of(self).add("AutoCleanup", "true")
    
    def _create_secrets(self) -> None:
        """Create Secrets Manager secret with environment-specific naming."""
        self.google_oauth_secret = secretsmanager.Secret(
            self,
            "GoogleOAuthSecret",
            secret_name=f"{self.config.resource_prefix}-google-oauth",
            description=f"Google OAuth credentials for {self.config.branch}",
            secret_object_value={
                "client_id": SecretValue.unsafe_plain_text(
                    os.getenv("GOOGLE_OAUTH_CLIENT_ID")
                ),
                "client_secret": SecretValue.unsafe_plain_text(
                    os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
                ),
            },
        )
    
    def _create_user_pool(self) -> None:
        """Create Cognito User Pool with environment-specific naming."""
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{self.config.resource_prefix}-user-pool",
            sign_in_aliases=cognito.SignInAliases(email=True),
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # ... rest of configuration
            removal_policy=self._get_removal_policy()
        )
        
        # Create User Pool Client with environment-specific callback URLs
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "UserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"{self.config.resource_prefix}-client",
            # ... rest of configuration
        )
        
        # Create domain with environment-specific prefix
        self.user_pool_domain = cognito.UserPoolDomain(
            self,
            "UserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{self.config.resource_prefix}"
            ),
        )
    
    def _get_removal_policy(self) -> RemovalPolicy:
        """Get appropriate removal policy based on environment."""
        if self.config.environment in ["feature", "dev"]:
            return RemovalPolicy.DESTROY
        else:
            return RemovalPolicy.RETAIN
    
    def _create_outputs(self) -> None:
        """Create stack outputs for cross-stack references."""
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name=f"{self.config.stack_prefix}-user-pool-id",
            description=f"User Pool ID for {self.config.branch}"
        )
        
        CfnOutput(
            self,
            "UserPoolClientId", 
            value=self.user_pool_client.user_pool_client_id,
            export_name=f"{self.config.stack_prefix}-client-id",
            description=f"User Pool Client ID for {self.config.branch}"
        )
        
        CfnOutput(
            self,
            "CognitoDomain",
            value=self.user_pool_domain.domain_name,
            export_name=f"{self.config.stack_prefix}-cognito-domain",
            description=f"Cognito domain for {self.config.branch}"
        )
```

**Enhanced `cdk/static_site_stack.py`**
```python
import os
from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
    Tags,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from constructs import Construct

from .config import DeploymentConfig
from .auth_stack import AuthStack


class StaticSiteStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        config: DeploymentConfig,
        auth_stack: AuthStack,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.config = config
        self.auth_stack = auth_stack
        
        # Apply consistent tagging
        self._apply_tags()
        
        # Create environment-specific resources
        self._create_lambda_edge()
        self._create_s3_bucket()
        self._create_cloudfront()
        self._create_deployment()
        self._create_outputs()
    
    def _apply_tags(self) -> None:
        """Apply consistent tags for resource management."""
        Tags.of(self).add("Environment", self.config.environment)
        Tags.of(self).add("Branch", self.config.branch)
        Tags.of(self).add("Project", "sflt")
        Tags.of(self).add("ManagedBy", "cdk")
        
        if self.config.environment == "feature":
            Tags.of(self).add("FeatureBranch", self.config.branch)
            Tags.of(self).add("AutoCleanup", "true")
    
    def _create_lambda_edge(self) -> None:
        """Create Lambda@Edge function with environment-specific naming."""
        self.auth_lambda = lambda_.Function(
            self,
            "AuthLambda",
            function_name=f"{self.config.resource_prefix}-auth-edge",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="auth_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "lambda-edge")
            ),
            description=f"Lambda@Edge for {self.config.branch} auth",
            timeout=Duration.seconds(5),
            memory_size=128,
        )
        
        # Environment-specific versioning
        self.auth_lambda_version = self.auth_lambda.current_version
    
    def _create_s3_bucket(self) -> None:
        """Create S3 bucket with environment-specific naming."""
        self.bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"{self.config.resource_prefix}-website-{self.account}",
            website_index_document="index.html",
            website_error_document="error.html",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=self._get_removal_policy(),
            auto_delete_objects=self.config.environment in ["feature", "dev"]
        )
    
    def _create_cloudfront(self) -> None:
        """Create CloudFront distribution with environment-specific configuration."""
        # Import auth stack values using cross-region references
        user_pool_id = Fn.import_value(f"{self.config.stack_prefix}-user-pool-id")
        client_id = Fn.import_value(f"{self.config.stack_prefix}-client-id")
        cognito_domain = Fn.import_value(f"{self.config.stack_prefix}-cognito-domain")
        
        # Create distribution
        self.distribution = cloudfront.CloudFrontWebDistribution(
            self,
            "Distribution",
            # ... CloudFront configuration with Lambda@Edge
            comment=f"Distribution for {self.config.branch} branch"
        )
    
    def _get_removal_policy(self) -> RemovalPolicy:
        """Get appropriate removal policy based on environment."""
        if self.config.environment in ["feature", "dev"]:
            return RemovalPolicy.DESTROY
        else:
            return RemovalPolicy.RETAIN
    
    def _create_outputs(self) -> None:
        """Create stack outputs."""
        CfnOutput(
            self,
            "DistributionDomainName",
            value=self.distribution.distribution_domain_name,
            export_name=f"{self.config.stack_prefix}-distribution-domain",
            description=f"CloudFront domain for {self.config.branch}"
        )
        
        CfnOutput(
            self,
            "S3BucketName",
            value=self.bucket.bucket_name,
            export_name=f"{self.config.stack_prefix}-bucket-name",
            description=f"S3 bucket for {self.config.branch}"
        )
```

#### 4. Environment-Aware Scripts

**Enhanced `scripts/generate_aws_exports.py`**
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Generate aws-exports.js from CDK stack outputs for any environment."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import boto3
from rich.console import Console
from rich.logging import RichHandler

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cdk.config import get_deployment_config

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)

def main():
    """Generate aws-exports.js for current environment."""
    config = get_deployment_config()
    
    console.rule(f"[bold blue]Generating AWS Exports for {config.environment}[/bold blue]")
    logger.info(f"Branch: [cyan]{config.branch}[/cyan]")
    logger.info(f"Auth Stack: [yellow]{config.auth_stack_name}[/yellow]")
    logger.info(f"Site Stack: [yellow]{config.static_site_stack_name}[/yellow]")
    
    # Get stack outputs using environment-specific stack names
    auth_outputs = get_stack_outputs(config.auth_stack_name, config.auth_region)
    static_outputs = get_stack_outputs(config.static_site_stack_name, config.site_region)
    
    if not auth_outputs or not static_outputs:
        console.print("[red]✗[/red] Failed to get required stack outputs")
        return 1
    
    # Generate aws-exports.js
    aws_exports = generate_aws_exports(auth_outputs, static_outputs, config)
    
    # Write to file
    frontend_dir = Path(__file__).parent.parent / "frontend"
    exports_file = frontend_dir / "src" / "aws-exports.js"
    
    with open(exports_file, 'w') as f:
        f.write(aws_exports)
    
    console.print(f"[green]✓[/green] Generated [cyan]{exports_file}[/cyan]")
    console.print(f"[green]✓[/green] Environment: [yellow]{config.environment}[/yellow]")
    
    return 0

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

def generate_aws_exports(auth_outputs: dict, static_outputs: dict, config) -> str:
    """Generate aws-exports.js content."""
    cloudfront_domain = static_outputs.get("DistributionDomainName", "")
    
    exports = {
        "aws_project_region": config.auth_region,
        "aws_cognito_region": config.auth_region,
        "aws_user_pools_id": auth_outputs.get("UserPoolId", ""),
        "aws_user_pools_web_client_id": auth_outputs.get("UserPoolClientId", ""),
        "aws_cognito_identity_pool_id": "",  # Not using identity pool
        "aws_mandatory_sign_in": "enable",
        "aws_cognito_sign_up_enabled": "enable",
        "aws_cognito_username_configuration": {
            "aliases": ["email"]
        },
        "aws_cognito_social_providers": ["Google"],
        "aws_cognito_password_protection_settings": {
            "passwordPolicyMinLength": 8,
            "passwordPolicyCharacters": []
        },
        "oauth": {
            "domain": auth_outputs.get("CognitoDomain", ""),
            "scope": [
                "phone", "email", "openid", "profile", 
                "https://www.googleapis.com/auth/calendar"
            ],
            "redirectSignIn": f"https://{cloudfront_domain}/",
            "redirectSignOut": f"https://{cloudfront_domain}/",
            "responseType": "code"
        },
        "federationTarget": "COGNITO_USER_POOLS",
        "aws_appsync_graphqlEndpoint": "",
        "aws_appsync_region": config.auth_region,
        "aws_appsync_authenticationType": "AMAZON_COGNITO_USER_POOLS",
        
        # Environment-specific configuration
        "environment": config.environment,
        "branch": config.branch,
        "cloudfront_domain": cloudfront_domain
    }
    
    return f"""const awsExports = {json.dumps(exports, indent=2)};
export default awsExports;
"""

if __name__ == "__main__":
    sys.exit(main())
```

#### 5. Enhanced Makefile for Environment Management

**Enhanced Makefile targets:**
```makefile
# Get current branch for dynamic stack naming
BRANCH := $(shell git rev-parse --abbrev-ref HEAD)
STACK_PREFIX := sflt-$(shell echo $(BRANCH) | tr '/' '-' | tr '_' '-' | tr '[:upper:]' '[:lower:]')

# Environment-aware deployment targets
deploy-feature: export GIT_BRANCH=$(BRANCH)
deploy-feature: build
	@echo "Deploying feature branch: $(BRANCH)"
	@echo "Stack prefix: $(STACK_PREFIX)"
	uv run cdk deploy --all --require-approval never

# Clean deployment for current branch
deploy-clean: export GIT_BRANCH=$(BRANCH)
deploy-clean:
	@echo "Destroying feature branch: $(BRANCH)"
	@echo "Stack prefix: $(STACK_PREFIX)"
	uv run cdk destroy --all --force

# List all feature branch stacks
list-feature-stacks:
	@echo "=== Feature Branch Stacks ==="
	@aws cloudformation list-stacks --region ap-southeast-2 --query 'StackSummaries[?contains(StackName, `sflt-`) && StackStatus != `DELETE_COMPLETE`].[StackName,StackStatus,CreationTime]' --output table
	@aws cloudformation list-stacks --region us-east-1 --query 'StackSummaries[?contains(StackName, `sflt-`) && StackStatus != `DELETE_COMPLETE`].[StackName,StackStatus,CreationTime]' --output table

# Cleanup old feature branches
cleanup-feature-branches:
	@echo "Finding old feature branch stacks..."
	@uv run scripts/cleanup_feature_branches.py

# Environment-aware aws-exports generation
generate-aws-exports: export GIT_BRANCH=$(BRANCH)
generate-aws-exports:
	@echo "Generating aws-exports for branch: $(BRANCH)"
	uv run scripts/generate_aws_exports.py

# Environment-aware Lambda code generation
generate-lambda-code: export GIT_BRANCH=$(BRANCH)
generate-lambda-code:
	@echo "Generating Lambda code for branch: $(BRANCH)"
	uv run scripts/generate_lambda_code.py
```

#### 6. Feature Branch Cleanup Script

**New `scripts/cleanup_feature_branches.py`**
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
# ]
# ///
"""Cleanup old feature branch CDK stacks."""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import boto3
from rich.console import Console
from rich.table import Table

console = Console()

def main():
    """Cleanup old feature branch stacks."""
    console.rule("[bold red]Feature Branch Cleanup[/bold red]")
    
    # Get active branches
    active_branches = get_active_git_branches()
    console.print(f"Active branches: {', '.join(active_branches)}")
    
    # Find stacks in both regions
    regions = ["ap-southeast-2", "us-east-1"]
    old_stacks = []
    
    for region in regions:
        stacks = find_feature_stacks(region, active_branches)
        old_stacks.extend(stacks)
    
    if not old_stacks:
        console.print("[green]✓[/green] No old feature branch stacks found")
        return 0
    
    # Display stacks to be deleted
    table = Table(title="Stacks to Delete")
    table.add_column("Stack Name")
    table.add_column("Region")
    table.add_column("Age (days)")
    table.add_column("Status")
    
    for stack in old_stacks:
        age_days = (datetime.now() - stack['creation_time']).days
        table.add_row(
            stack['name'], 
            stack['region'], 
            str(age_days),
            stack['status']
        )
    
    console.print(table)
    
    # Confirm deletion
    if not console.input("Delete these stacks? (y/N): ").lower().startswith('y'):
        console.print("Cancelled")
        return 0
    
    # Delete stacks
    for stack in old_stacks:
        delete_stack(stack['name'], stack['region'])
    
    return 0

def get_active_git_branches() -> List[str]:
    """Get list of active git branches."""
    try:
        # Get remote branches
        result = subprocess.run(
            ["git", "branch", "-r"],
            capture_output=True,
            text=True,
            check=True
        )
        
        branches = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith('origin/HEAD'):
                branch = line.replace('origin/', '')
                branches.append(branch)
        
        return branches
    except subprocess.CalledProcessError:
        console.print("[yellow]Warning: Could not get git branches[/yellow]")
        return []

def find_feature_stacks(region: str, active_branches: List[str]) -> List[dict]:
    """Find old feature branch stacks in a region."""
    cf_client = boto3.client("cloudformation", region_name=region)
    
    try:
        response = cf_client.list_stacks(
            StackStatusFilter=[
                'CREATE_COMPLETE',
                'UPDATE_COMPLETE', 
                'ROLLBACK_COMPLETE',
                'UPDATE_ROLLBACK_COMPLETE'
            ]
        )
        
        old_stacks = []
        cutoff_date = datetime.now() - timedelta(days=7)  # Consider stacks older than 7 days
        
        for stack in response['StackSummaries']:
            stack_name = stack['StackName']
            
            # Check if it's a feature branch stack
            if not stack_name.startswith('sflt-'):
                continue
                
            # Skip main/develop stacks
            if 'sflt-main' in stack_name or 'sflt-develop' in stack_name:
                continue
            
            # Extract branch name from stack name
            branch_from_stack = extract_branch_from_stack_name(stack_name)
            
            # Check if branch is still active
            if branch_from_stack in active_branches:
                continue
            
            # Check if stack is old enough
            if stack['CreationTime'].replace(tzinfo=None) > cutoff_date:
                continue
            
            old_stacks.append({
                'name': stack_name,
                'region': region,
                'creation_time': stack['CreationTime'].replace(tzinfo=None),
                'status': stack['StackStatus']
            })
        
        return old_stacks
        
    except Exception as e:
        console.print(f"[red]Error finding stacks in {region}: {e}[/red]")
        return []

def extract_branch_from_stack_name(stack_name: str) -> str:
    """Extract branch name from stack name."""
    # Remove 'sflt-' prefix and stack suffix
    if stack_name.startswith('sflt-'):
        branch_part = stack_name[5:]  # Remove 'sflt-'
        
        # Remove common suffixes
        if branch_part.endswith('-auth'):
            branch_part = branch_part[:-5]
        elif branch_part.endswith('-site'):
            branch_part = branch_part[:-5]
        
        # Convert back to branch format
        return branch_part.replace('-', '/')

def delete_stack(stack_name: str, region: str):
    """Delete a CloudFormation stack."""
    console.print(f"Deleting {stack_name} in {region}...")
    
    cf_client = boto3.client("cloudformation", region_name=region)
    
    try:
        cf_client.delete_stack(StackName=stack_name)
        console.print(f"[green]✓[/green] Started deletion of {stack_name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to delete {stack_name}: {e}")

if __name__ == "__main__":
    sys.exit(main())
```

## Usage Examples

### Deploying a Feature Branch

```bash
# Switch to feature branch
git checkout feature/calendar-integration

# Deploy feature branch (automatically gets sflt-feature-calendar-integration prefix)
export AWS_PROFILE=sflt
make deploy-feature

# Generated stack names:
# - sflt-feature-calendar-integration-auth (ap-southeast-2)
# - sflt-feature-calendar-integration-site (us-east-1)
```

### Parallel Development

```bash
# Developer 1 - Feature A
git checkout feature/auth-enhancement
make deploy-feature

# Developer 2 - Feature B  
git checkout feature/ui-improvements
make deploy-feature

# No conflicts - completely isolated stacks
```

### Cleanup

```bash
# List all feature branch stacks
make list-feature-stacks

# Clean up current branch
make deploy-clean

# Clean up old/merged branches automatically
make cleanup-feature-branches
```

## Benefits of This Approach

### ✅ Complete Isolation
- Each branch gets independent stacks with unique names
- No resource conflicts between branches
- Cross-region dependencies work within branch scope

### ✅ Easy Cleanup
- Automatic detection of merged/deleted branches
- Batch cleanup of old stacks
- Resource tagging for automated policies

### ✅ Developer Experience
- Simple `make deploy-feature` command
- Automatic environment detection from git branch
- No manual configuration needed

### ✅ Cost Management
- Feature branches use DESTROY removal policy
- Automatic cleanup of old resources
- Clear resource attribution via tags

### ✅ Production Safety
- Main/develop branches use RETAIN policy
- Environment-specific security controls
- Clear separation between environments

## Alternative Approaches Considered

### 1. CDK Pipelines Approach
**Pros**: Built-in branch management, automated testing
**Cons**: Complex setup, requires CodePipeline infrastructure, overkill for current needs

### 2. Multiple AWS Accounts
**Pros**: Complete isolation, clear billing separation
**Cons**: Complex cross-account setup, higher management overhead, Lambda@Edge cross-region complexity

### 3. Resource Suffix Approach
**Pros**: Simpler than full environment system
**Cons**: Still prone to conflicts, harder to manage cleanup, no environment-specific policies

## Conclusion

The **Environment-Based Feature Branch Isolation** approach provides the best balance of:
- Complete resource isolation
- Simple developer experience  
- Easy cleanup and cost management
- Maintained infrastructure integrity
- Support for parallel development

This solution transforms the current fixed-name infrastructure into a flexible, multi-environment system while preserving all existing functionality and deployment patterns.