#!/usr/bin/env python3
"""Environment configuration for feature branch deployments."""

import os
import subprocess
from dataclasses import dataclass


@dataclass
class DeploymentConfig:
    """Configuration for a deployment environment."""

    environment: str  # dev, staging, prod, feature-branch-name
    branch: str  # git branch name
    aws_profile: str  # AWS profile to use
    account: str  # AWS account ID
    auth_region: str  # Region for auth stack
    site_region: str  # Region for static site (must be us-east-1 for Lambda@Edge)

    @property
    def stack_prefix(self) -> str:
        """Generate stack prefix for this environment."""
        # Sanitize branch name for AWS resources
        sanitized = self.branch.replace("/", "-").replace("_", "-").lower()
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
    """Get deployment configuration from git and environment variables."""

    # Always check git first, then fall back to environment variable
    branch = get_git_branch()
    if branch == "unknown":
        branch = os.getenv("GIT_BRANCH", "unknown")

    environment = determine_environment(branch)

    return DeploymentConfig(
        environment=environment,
        branch=branch,
        aws_profile=os.getenv("AWS_PROFILE", "sflt"),
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        auth_region=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"),
        site_region="us-east-1",  # Required for Lambda@Edge
    )


def get_git_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
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
