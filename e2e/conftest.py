"""Pytest configuration for e2e tests."""

import os

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page

# Load environment variables
load_dotenv()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override browser context arguments."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
def cloudfront_url():
    """Get the CloudFront URL from environment or AWS."""
    url = os.getenv("CLOUDFRONT_URL")

    if not url:
        # Try to get it from AWS CloudFormation
        import subprocess

        try:
            result = subprocess.run(
                [
                    "aws",
                    "cloudformation",
                    "describe-stacks",
                    "--stack-name",
                    "SfltStaticSiteStack",
                    "--region",
                    "us-east-1",  # StaticSiteStack is now in us-east-1
                    "--query",
                    "Stacks[0].Outputs[?OutputKey=='DistributionDomainName'].OutputValue",
                    "--output",
                    "text",
                ],
                env={**os.environ, "AWS_PROFILE": os.getenv("AWS_PROFILE", "sflt")},
                capture_output=True,
                text=True,
                check=True,
            )
            domain = result.stdout.strip()
            if domain:
                url = f"https://{domain}"
        except subprocess.CalledProcessError:
            # Fallback to localhost for local testing
            url = "http://localhost:5173"

    return url


@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """Return a page that's ready for testing."""
    # Add any authentication or setup here if needed
    return page
