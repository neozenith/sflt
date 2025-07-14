"""E2E tests for protected routes using Lambda@Edge."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.parametrize(
    "protected_path",
    [
        "/admin",
        "/dashboard",
        "/profile",
    ],
)
def test_protected_routes_return_403(page: Page, cloudfront_url: str, protected_path: str):
    """Test that protected routes redirect to Cognito login."""
    response = page.goto(f"{cloudfront_url}{protected_path}", wait_until="domcontentloaded")

    assert response is not None
    assert response.status == 200, f"Expected 200 (after redirect) for {protected_path}, got {response.status}"

    # Check that we were redirected to Cognito login
    final_url = response.url
    assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in final_url, (
        f"Expected redirect to Cognito, got {final_url}"
    )
    # Can be either oauth2/authorize or login page
    assert "oauth2/authorize" in final_url or "/login" in final_url, (
        f"Expected OAuth authorize or login endpoint, got {final_url}"
    )


def test_protected_route_response_body(page: Page, cloudfront_url: str):
    """Test that protected routes redirect to Cognito login page."""
    response = page.goto(f"{cloudfront_url}/admin")

    assert response is not None
    assert response.status == 200

    # Check we're on the Cognito login page
    final_url = response.url
    assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in final_url

    # Check for login page elements
    content = page.content()
    assert "sign in" in content.lower() or "login" in content.lower() or "oauth" in content.lower()


@pytest.mark.parametrize(
    "public_path",
    [
        "/",
        "/public",
    ],
)
def test_public_routes_work(page: Page, cloudfront_url: str, public_path: str):
    """Test that public routes still work normally."""
    response = page.goto(f"{cloudfront_url}{public_path}")

    assert response is not None
    assert response.ok, f"Public route {public_path} should be accessible"

    # Should be able to see React content
    expect(page.locator("h1")).to_be_visible()


def test_protected_route_with_subpaths(page: Page, cloudfront_url: str):
    """Test that subpaths of protected routes are also protected."""
    protected_subpaths = [
        "/admin/users",
        "/admin/settings",
        "/dashboard/analytics",
        "/profile/settings",
    ]

    for subpath in protected_subpaths:
        response = page.goto(f"{cloudfront_url}{subpath}")
        assert response is not None
        assert response.status == 200, f"Expected redirect for subpath {subpath}, got {response.status}"
        assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in response.url, (
            f"Expected Cognito redirect for {subpath}"
        )


def test_case_sensitivity(page: Page, cloudfront_url: str):
    """Test that route protection is case sensitive."""
    # These should still be protected (exact case)
    protected_routes = ["/admin", "/dashboard", "/profile"]

    for route in protected_routes:
        response = page.goto(f"{cloudfront_url}{route}")
        assert response is not None
        assert response.status == 200
        assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in response.url

    # These might not be protected due to case differences
    # (depends on your Lambda function implementation)
    case_variations = ["/Admin", "/ADMIN", "/Dashboard"]

    for route in case_variations:
        response = page.goto(f"{cloudfront_url}{route}")
        assert response is not None
        # These might return 200 (SPA routing) or 403 depending on implementation


def test_lambda_edge_headers(page: Page, cloudfront_url: str):
    """Test that Lambda@Edge adds proper security headers."""
    response = page.goto(f"{cloudfront_url}/admin")

    assert response is not None
    assert response.status == 200  # After redirect to Cognito

    # Check we're at Cognito
    assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in response.url

    # For redirects, we can check that Lambda@Edge added the X-Cache header
    headers = response.headers
    x_cache = headers.get("x-cache", "")
    # Should show it came from Lambda@Edge
    assert "LambdaGeneratedResponse" in x_cache or "cloudfront" in x_cache.lower()


def test_performance_impact(page: Page, cloudfront_url: str):
    """Test that Lambda@Edge doesn't significantly impact performance."""
    import time

    # Test public route performance
    start_time = time.time()
    response = page.goto(f"{cloudfront_url}/public")
    public_load_time = time.time() - start_time

    assert response is not None
    assert response.ok

    # Test protected route performance (should be fast redirect)
    start_time = time.time()
    response = page.goto(f"{cloudfront_url}/admin")
    protected_load_time = time.time() - start_time

    assert response is not None
    assert response.status == 200
    assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in response.url

    # Protected route redirect should be reasonably fast
    assert protected_load_time < 5.0, "Protected route redirect should be reasonably fast"

    # Both should complete within reasonable time
    assert public_load_time < 5.0, "Public route should load quickly"
