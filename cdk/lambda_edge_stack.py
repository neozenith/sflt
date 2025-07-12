import os

from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from constructs import Construct


class LambdaEdgeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda@Edge function for route protection
        # This stack MUST be deployed in us-east-1
        self.auth_lambda = lambda_.Function(
            self,
            "AuthLambda",
            function_name="SfltAuthLambdaEdgeV5",  # Explicit name for cross-environment access
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="auth_handler.handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "lambda-edge")),
            description="Lambda@Edge function for protecting routes",
            timeout=Duration.seconds(5),
            memory_size=128,
        )

        # Create a version for Lambda@Edge (required for CloudFront)
        self.auth_lambda_version = lambda_.Version(
            self,
            "AuthLambdaVersion",
            lambda_=self.auth_lambda,
        )

        # Grant the Lambda VERSION permission to be used by CloudFront
        # This is required due to AWS Lambda authorization changes
        self.auth_lambda_version.add_permission(
            "AllowCloudFrontInvoke",
            principal=iam.ServicePrincipal("edgelambda.amazonaws.com"),
            action="lambda:InvokeFunction",
        )
