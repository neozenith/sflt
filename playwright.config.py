"""Playwright configuration for e2e tests."""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def pytest_configure(config):
    """Configure pytest with Playwright settings."""
    # Get CloudFront URL from environment or use localhost for local testing
    base_url = os.getenv("E2E_BASE_URL", "http://localhost:5173")

    # Set the base URL for tests
    config.option.base_url = base_url


# Playwright browser configurations
BROWSER_OPTIONS: dict[str, dict] = {
    "chromium": {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    },
    "firefox": {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    },
    "webkit": {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    },
}

# Test configuration
TEST_CONFIG = {
    "timeout": 30000,  # 30 seconds
    "retries": 2,
    "workers": 1,  # Run tests sequentially
    "headed": os.getenv("HEADED", "false").lower() == "true",
    "slow_mo": int(os.getenv("SLOW_MO", "0")),
}
