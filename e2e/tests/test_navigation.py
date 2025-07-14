"""E2E tests for React navigation and routing."""

from playwright.sync_api import Page, expect


def test_navigation_links_present(page: Page, cloudfront_url: str):
    """Test that navigation links are present on the homepage."""
    page.goto(cloudfront_url)

    # Check that navigation is visible
    nav = page.locator("nav.navigation")
    expect(nav).to_be_visible()

    # Check for navigation links - only public when not authenticated
    nav_links = page.locator(".nav-links a")
    expect(nav_links).to_have_count(2)  # Only Home and Public when not authenticated

    # Check public links
    expect(page.locator("text=Home")).to_be_visible()
    expect(page.locator("text=Public")).to_be_visible()

    # Check for Sign In button (since user is not authenticated)
    expect(page.locator("text=Sign In with Google")).to_be_visible()

    # Protected links should NOT be visible when not authenticated
    expect(page.locator("text=Admin")).not_to_be_visible()
    expect(page.locator("text=Dashboard")).not_to_be_visible()
    expect(page.locator("text=Profile")).not_to_be_visible()


def test_public_navigation_works(page: Page, cloudfront_url: str):
    """Test that public navigation works correctly."""
    page.goto(cloudfront_url)

    # Click on Public link
    page.locator("text=Public").click()

    # Should navigate to public page
    expect(page.locator("h1")).to_have_text("Public Page")
    expect(page.locator("text=This is a public page")).to_be_visible()

    # URL should update (client-side routing)
    expect(page).to_have_url(f"{cloudfront_url}/public")


def test_home_navigation(page: Page, cloudfront_url: str):
    """Test navigation back to home page."""
    page.goto(f"{cloudfront_url}/public")

    # Click Home link
    page.locator("text=Home").click()

    # Should be back on home page
    expect(page.locator("h1")).to_have_text("Welcome to SFLT")
    expect(page.locator("button:has-text('Count is')")).to_have_text("Count is 0")
    expect(page).to_have_url(cloudfront_url + "/")


def test_protected_links_attempt_navigation(page: Page, cloudfront_url: str):
    """Test that direct navigation to protected routes redirects to Cognito login."""
    # Admin links are not visible when not authenticated, so test direct navigation
    page.goto(f"{cloudfront_url}/admin")

    # Should redirect to Cognito login
    page.wait_for_load_state("networkidle")
    final_url = page.url
    assert "sflt-auth.auth.ap-southeast-2.amazoncognito.com" in final_url


def test_direct_url_access_public(page: Page, cloudfront_url: str):
    """Test that direct URL access to public routes works."""
    # Direct access to public route
    page.goto(f"{cloudfront_url}/public")

    expect(page.locator("h1")).to_have_text("Public Page")
    expect(page.locator("text=Open to all visitors")).to_be_visible()


def test_counter_functionality_preserved(page: Page, cloudfront_url: str):
    """Test that the original counter functionality still works."""
    page.goto(cloudfront_url)

    # Find and test the counter (not the auth button)
    button = page.locator("button:has-text('Count is')")
    expect(button).to_have_text("Count is 0")

    # Click multiple times
    for i in range(1, 4):
        button.click()
        expect(button).to_have_text(f"Count is {i}")


def test_responsive_navigation(page: Page, cloudfront_url: str):
    """Test that navigation works on different screen sizes."""
    page.goto(cloudfront_url)

    # Test on mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})

    # Navigation should still be visible
    nav = page.locator("nav.navigation")
    expect(nav).to_be_visible()

    # Links should still be clickable
    expect(page.locator("text=Public")).to_be_visible()

    # Test navigation still works
    page.locator("text=Public").click()
    expect(page.locator("h1")).to_have_text("Public Page")


def test_browser_back_button(page: Page, cloudfront_url: str):
    """Test that browser back button works with client-side routing."""
    page.goto(cloudfront_url)

    # Navigate to public page
    page.locator("text=Public").click()
    expect(page.locator("h1")).to_have_text("Public Page")

    # Use browser back button
    page.go_back()

    # Should be back on home page
    expect(page.locator("h1")).to_have_text("Welcome to SFLT")
    expect(page.locator("button:has-text('Count is')")).to_be_visible()
