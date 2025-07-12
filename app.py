#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from cdk.auth_stack import AuthStack
from cdk.static_site_stack import StaticSiteStack

# Load environment variables from .env file
load_dotenv()

app = cdk.App()

# Enable cross-region references
env_context = {"@aws-cdk/core:enableDiffNoFail": True, "aws:cdk:enable-cross-region-references": True}

# Authentication stack in your preferred region
auth_stack = AuthStack(
    app,
    "SfltAuthStack",
    cloudfront_domain=None,  # Will be populated after first deployment
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("CDK_DEFAULT_REGION", "ap-southeast-2")),
    ),
    description="Authentication infrastructure with Cognito and Google OAuth",
)

# Static site stack with integrated Lambda@Edge (MUST be in us-east-1)
static_site_stack = StaticSiteStack(
    app,
    "SfltStaticSiteStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region="us-east-1",  # Required for Lambda@Edge
    ),
    description="Static React website deployed to CloudFront with S3 origin and integrated Lambda@Edge",
)

app.synth()
