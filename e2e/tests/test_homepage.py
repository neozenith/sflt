"""E2E tests for the homepage."""

import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page, cloudfront_url: str):
    """Test that the homepage loads successfully."""
    # Navigate to the site
    page.goto(cloudfront_url)

    # Check that the page title is correct
    expect(page).to_have_title("SFLT - Static Site")

    # Check that the main heading is visible
    heading = page.locator("h1")
    expect(heading).to_be_visible()
    expect(heading).to_have_text("Welcome to SFLT")


def test_homepage_content(page: Page, cloudfront_url: str):
    """Test that the homepage has the expected content."""
    page.goto(cloudfront_url)

    # Check for the description text
    description = page.locator("text=Static React site deployed with AWS CDK to CloudFront + S3")
    expect(description).to_be_visible()

    # Check for the OAC description
    oac_text = page.locator("text=This site is hosted on S3 and served through CloudFront using Origin Access Control")
    expect(oac_text).to_be_visible()


def test_counter_functionality(page: Page, cloudfront_url: str):
    """Test that the counter button works correctly."""
    page.goto(cloudfront_url)

    # Find the counter button specifically (not the auth button)
    button = page.locator("button:has-text('Count is')")
    expect(button).to_be_visible()
    expect(button).to_have_text("Count is 0")

    # Click the button and check that the count increases
    button.click()
    expect(button).to_have_text("Count is 1")

    # Click again
    button.click()
    expect(button).to_have_text("Count is 2")

    # Click multiple times
    for _ in range(3):
        button.click()
    expect(button).to_have_text("Count is 5")


def test_responsive_design(page: Page, cloudfront_url: str):
    """Test that the site is responsive."""
    page.goto(cloudfront_url)

    # Test desktop viewport
    page.set_viewport_size({"width": 1920, "height": 1080})
    expect(page.locator("h1")).to_be_visible()

    # Test tablet viewport
    page.set_viewport_size({"width": 768, "height": 1024})
    expect(page.locator("h1")).to_be_visible()

    # Test mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    expect(page.locator("h1")).to_be_visible()

    # Check that content is still accessible on mobile
    button = page.locator("button:has-text('Count is')")
    expect(button).to_be_visible()


def test_cloudfront_headers(page: Page, cloudfront_url: str):
    """Test that CloudFront is serving the content with proper headers."""
    response = page.goto(cloudfront_url)

    assert response is not None
    assert response.ok

    # Check for CloudFront headers
    headers = response.headers

    # CloudFront should add these headers
    assert "x-cache" in headers or "x-amz-cf-id" in headers or "x-amz-cf-pop" in headers

    # Check that HTTPS redirect is working (if accessing via HTTP)
    assert response.url.startswith("https://")


@pytest.mark.parametrize("path", ["/", "/nonexistent", "/about", "/contact"])
def test_spa_routing(page: Page, cloudfront_url: str, path: str):
    """Test that SPA routing works correctly (all routes return index.html)."""
    response = page.goto(f"{cloudfront_url}{path}")

    assert response is not None
    assert response.ok

    # All routes should load the React app
    expect(page.locator("h1")).to_be_visible()
    expect(page).to_have_title("SFLT - Static Site")
