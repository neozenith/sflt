#!/usr/bin/env python3

import aws_cdk as cdk
from dotenv import load_dotenv

from cdk.auth_stack import AuthStack
from cdk.config import get_deployment_config
from cdk.static_site_stack import StaticSiteStack

# Load environment variables from .env file
load_dotenv()

# Get deployment configuration
config = get_deployment_config()

app = cdk.App()

# Add deployment context
app.node.set_context(
    "deployment:config",
    {"environment": config.environment, "branch": config.branch, "stackPrefix": config.stack_prefix},
)

print(f"🚀 Deploying {config.environment} environment for branch: {config.branch}")
print(f"📦 Stack prefix: {config.stack_prefix}")

# Enable cross-region references
env_context = {"@aws-cdk/core:enableDiffNoFail": True, "aws:cdk:enable-cross-region-references": True}

# Authentication stack in your preferred region
auth_stack = AuthStack(
    app,
    config.auth_stack_name,
    config=config,
    cloudfront_domain=None,  # Will be populated after first deployment
    env=cdk.Environment(
        account=config.account,
        region=config.auth_region,
    ),
    description=f"Authentication infrastructure for {config.branch} branch",
)

# Static site stack with integrated Lambda@Edge (MUST be in us-east-1)
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
