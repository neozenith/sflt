import os

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
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


class StaticSiteStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda@Edge function for route protection
        # This stack MUST be deployed in us-east-1 for Lambda@Edge
        auth_lambda = lambda_.Function(
            self,
            "AuthLambda",
            function_name="SfltAuthLambdaEdgeV6",  # New version to avoid conflicts
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="auth_handler.handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "lambda-edge")),
            description="Lambda@Edge function for protecting routes",
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
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create Origin Access Control for CloudFront
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "OAC",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="SfltOAC",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4",
                description="OAC for static website",
            ),
        )

        # Create Lambda@Edge association for viewer request
        edge_lambdas = [
            cloudfront.EdgeLambda(
                event_type=cloudfront.LambdaEdgeEventType.VIEWER_REQUEST,
                function_version=auth_lambda_version,
            )
        ]

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
            description="CloudFront distribution domain name",
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
            description="S3 bucket name",
        )
