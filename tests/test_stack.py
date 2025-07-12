import aws_cdk as cdk
from aws_cdk.assertions import Template

from cdk.static_site_stack import StaticSiteStack


def test_static_site_stack_creates_bucket():
    app = cdk.App()
    stack = StaticSiteStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Check that S3 bucket is created
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
            "VersioningConfiguration": {"Status": "Enabled"},
        },
    )


def test_static_site_stack_creates_cloudfront_distribution():
    app = cdk.App()
    stack = StaticSiteStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Check that CloudFront distribution is created
    template.resource_count_is("AWS::CloudFront::Distribution", 1)


def test_static_site_stack_creates_oac():
    app = cdk.App()
    stack = StaticSiteStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Check that Origin Access Control is created
    template.has_resource_properties(
        "AWS::CloudFront::OriginAccessControl",
        {
            "OriginAccessControlConfig": {
                "Name": "SfltOAC",
                "OriginAccessControlOriginType": "s3",
                "SigningBehavior": "always",
                "SigningProtocol": "sigv4",
            }
        },
    )
