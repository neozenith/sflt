import os

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    SecretValue,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

from .config import DeploymentConfig


class AuthStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: DeploymentConfig,
        cloudfront_domain: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config

        # Apply consistent tagging
        self._apply_tags()

        # Create Secrets Manager secret for Google OAuth credentials
        google_oauth_secret = secretsmanager.Secret(
            self,
            "GoogleOAuthSecret",
            secret_name=f"{self.config.resource_prefix}-google-oauth",
            description=f"Google OAuth credentials for {self.config.branch}",
            secret_object_value={
                "client_id": SecretValue.unsafe_plain_text(os.getenv("GOOGLE_OAUTH_CLIENT_ID")),
                "client_secret": SecretValue.unsafe_plain_text(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")),
            },
            removal_policy=self._get_removal_policy(),
        )

        # Create Cognito User Pool
        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{self.config.resource_prefix}-user-pool",
            sign_in_aliases=cognito.SignInAliases(email=True),
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=True, mutable=True),
                family_name=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "google_access_token": cognito.StringAttribute(min_len=1, max_len=2048),
                "google_refresh_token": cognito.StringAttribute(min_len=1, max_len=2048),
            },
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=self._get_removal_policy(),
        )

        # Create Google Identity Provider
        google_provider = cognito.UserPoolIdentityProviderGoogle(
            self,
            "GoogleProvider",
            user_pool=user_pool,
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret_value=SecretValue.unsafe_plain_text(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")),
            scopes=["openid", "email", "profile", "https://www.googleapis.com/auth/calendar"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.GOOGLE_EMAIL,
                given_name=cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
                family_name=cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
            ),
        )

        # Create Cognito User Pool Client with PKCE support
        user_pool_client = cognito.CfnUserPoolClient(
            self,
            "UserPoolClient",
            user_pool_id=user_pool.user_pool_id,
            client_name=f"{self.config.resource_prefix}-client",
            generate_secret=False,  # For public clients (SPA)
            explicit_auth_flows=[
                "ALLOW_USER_SRP_AUTH",
                "ALLOW_ADMIN_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
            allowed_o_auth_flows=["code"],
            allowed_o_auth_flows_user_pool_client=True,
            allowed_o_auth_scopes=["openid", "email", "profile"],
            callback_ur_ls=[
                "http://localhost:5173/",  # For local development
                "https://localhost:5173/",  # For local development with HTTPS
            ]
            + ([f"https://{cloudfront_domain}/"] if cloudfront_domain else []),
            logout_ur_ls=[
                "http://localhost:5173/",  # For local development
                "https://localhost:5173/",  # For local development with HTTPS
            ]
            + ([f"https://{cloudfront_domain}/"] if cloudfront_domain else []),
            supported_identity_providers=["Google", "COGNITO"],
            # Enable PKCE for secure authorization code flow without client secret
            prevent_user_existence_errors="ENABLED",
            enable_token_revocation=True,
            auth_session_validity=3,
        )

        # Ensure the client is created after the Google provider
        user_pool_client.node.add_dependency(google_provider)

        # Create Cognito Identity Pool
        identity_pool = cognito.CfnIdentityPool(
            self,
            "IdentityPool",
            identity_pool_name=f"{self.config.resource_prefix}_identity_pool".replace("-", "_"),
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=user_pool_client.ref,
                    provider_name=user_pool.user_pool_provider_name,
                )
            ],
        )

        # Create Cognito User Pool Domain
        user_pool_domain = cognito.UserPoolDomain(
            self,
            "UserPoolDomain",
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{self.config.resource_prefix}-auth"  # This will create {prefix}-auth.auth.region.amazoncognito.com
            ),
        )

        # Outputs
        CfnOutput(
            self,
            "UserPoolId",
            value=user_pool.user_pool_id,
            export_name=f"{self.config.stack_prefix}-user-pool-id",
            description=f"User Pool ID for {self.config.branch}",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=user_pool_client.ref,
            export_name=f"{self.config.stack_prefix}-client-id",
            description=f"User Pool Client ID for {self.config.branch}",
        )

        CfnOutput(
            self,
            "IdentityPoolId",
            value=identity_pool.ref,
            export_name=f"{self.config.stack_prefix}-identity-pool-id",
            description=f"Identity Pool ID for {self.config.branch}",
        )

        CfnOutput(
            self,
            "UserPoolDomainName",
            value=user_pool_domain.domain_name,
            export_name=f"{self.config.stack_prefix}-cognito-domain",
            description=f"Cognito domain for {self.config.branch}",
        )

        CfnOutput(
            self,
            "GoogleOAuthSecretArn",
            value=google_oauth_secret.secret_arn,
            description="Google OAuth credentials secret ARN",
        )

        # Store references for other stacks
        self.user_pool = user_pool
        self.user_pool_client = user_pool_client
        self.identity_pool = identity_pool
        self.google_oauth_secret = google_oauth_secret

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

    def _get_removal_policy(self) -> RemovalPolicy:
        """Get appropriate removal policy based on environment."""
        if self.config.environment in ["feature", "dev"]:
            return RemovalPolicy.DESTROY
        else:
            return RemovalPolicy.RETAIN
