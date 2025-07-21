import os

from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3_deployment,
)
from constructs import Construct

from .auth_stack import AuthStack
from .config import DeploymentConfig


class StaticSiteStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, config: DeploymentConfig, auth_stack: AuthStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        self.auth_stack = auth_stack

        # Apply consistent tagging
        self._apply_tags()

        # Create Lambda@Edge function for route protection
        # This stack MUST be deployed in us-east-1 for Lambda@Edge
        auth_lambda = lambda_.Function(
            self,
            "AuthLambda",
            function_name=f"{self.config.resource_prefix}-auth-edge",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="auth_handler.handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "lambda-edge")),
            description=f"Lambda@Edge for {self.config.branch} auth",
            timeout=Duration.seconds(5),
            memory_size=128,
        )

        # Create a version for Lambda@Edge (required for CloudFront)
        # Force new version when Lambda code changes by using file mtime
        import datetime

        auth_handler_path = os.path.join(os.path.dirname(__file__), "lambda-edge", "auth_handler.py")
        if os.path.exists(auth_handler_path):
            mtime = os.path.getmtime(auth_handler_path)
            version_description = (
                f"Lambda@Edge auth handler - {datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            version_description = f"Lambda@Edge auth handler - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        auth_lambda_version = lambda_.Version(
            self,
            "AuthLambdaVersion",
            lambda_=auth_lambda,
            description=version_description,
        )

        # Grant the Lambda VERSION permission to be used by CloudFront
        auth_lambda_version.add_permission(
            "AllowCloudFrontInvoke",
            principal=iam.ServicePrincipal("edgelambda.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        # Create S3 bucket for hosting static website content
        website_bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"{self.config.resource_prefix}-website-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=self._get_removal_policy(),
            auto_delete_objects=self.config.environment in ["feature", "dev"],
        )

        # Create Origin Access Control for CloudFront
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "OAC",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name=f"{self.config.resource_prefix}-oac",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4",
                description=f"OAC for {self.config.branch} static website",
            ),
        )

        # Create Lambda@Edge association for viewer request
        edge_lambdas = [
            cloudfront.EdgeLambda(
                event_type=cloudfront.LambdaEdgeEventType.VIEWER_REQUEST,
                function_version=auth_lambda_version,
            )
        ]

        # Import auth stack values using cross-region references
        user_pool_id = Fn.import_value(f"{self.config.stack_prefix}-user-pool-id")
        client_id = Fn.import_value(f"{self.config.stack_prefix}-client-id")
        cognito_domain = Fn.import_value(f"{self.config.stack_prefix}-cognito-domain")

        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin(
                    website_bucket,
                    origin_access_control_id=oac.attr_id,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                edge_lambdas=edge_lambdas,
            ),
            default_root_object="index.html",
            error_responses=[
                # Handle 404 errors (though with Lambda@Edge handling SPA routing,
                # this should rarely be needed)
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enabled=True,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            comment=f"Distribution for {self.config.branch} branch",
        )

        # Deploy website content to S3
        s3_deployment.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3_deployment.Source.asset("./frontend/build")],
            destination_bucket=website_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # Grant CloudFront access to S3 bucket
        website_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[website_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": (
                            f"arn:aws:cloudfront::{self.account}:distribution/{distribution.distribution_id}"
                        )
                    }
                },
            )
        )

        # Outputs
        CfnOutput(
            self,
            "DistributionDomainName",
            value=distribution.distribution_domain_name,
            export_name=f"{self.config.stack_prefix}-distribution-domain",
            description=f"CloudFront domain for {self.config.branch}",
        )

        CfnOutput(
            self,
            "DistributionId",
            value=distribution.distribution_id,
            description="CloudFront distribution ID",
        )

        CfnOutput(
            self,
            "AuthLambdaArn",
            value=auth_lambda_version.function_arn,
            description="Lambda@Edge function ARN for route protection",
        )

        CfnOutput(
            self,
            "BucketName",
            value=website_bucket.bucket_name,
            export_name=f"{self.config.stack_prefix}-bucket-name",
            description=f"S3 bucket for {self.config.branch}",
        )

    def _apply_tags(self) -> None:
        """Apply consistent tags for resource management."""
        Tags.of(self).add("Environment", self.config.environment)
        Tags.of(self).add("Branch", self.config.branch)
        Tags.of(self).add("Project", "sflt")
        Tags.of(self).add("ManagedBy", "cdk")

        if self.config.environment == "feature":
            Tags.of(self).add("FeatureBranch", self.config.branch)
            Tags.of(self).add("AutoCleanup", "true")

    def _get_removal_policy(self) -> RemovalPolicy:
        """Get appropriate removal policy based on environment."""
        if self.config.environment in ["feature", "dev"]:
            return RemovalPolicy.DESTROY
        else:
            return RemovalPolicy.RETAIN
