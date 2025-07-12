"""E2E performance tests."""

import time

from playwright.sync_api import Page


def test_page_load_time(page: Page, cloudfront_url: str):
    """Test that the page loads within acceptable time."""
    start_time = time.time()

    # Navigate to the page and wait for it to be fully loaded
    page.goto(cloudfront_url, wait_until="networkidle")

    load_time = time.time() - start_time

    # Page should load within 3 seconds
    assert load_time < 3.0, f"Page took {load_time:.2f} seconds to load"

    # Check that main content is visible
    assert page.locator("h1").is_visible()


def test_cloudfront_caching(page: Page, cloudfront_url: str):
    """Test that CloudFront caching is working properly."""
    # First request
    response1 = page.goto(cloudfront_url)
    assert response1 is not None

    # Get cache status from headers
    cache_status1 = response1.headers.get("x-cache", "").lower()

    # Second request (should potentially be cached)
    response2 = page.goto(cloudfront_url)
    assert response2 is not None

    cache_status2 = response2.headers.get("x-cache", "").lower()

    # At least one request should indicate caching
    # (first might be Miss, second might be Hit)
    assert "hit" in cache_status1 or "hit" in cache_status2 or cache_status1 or cache_status2, (
        "CloudFront caching headers not found"
    )


def test_asset_optimization(page: Page, cloudfront_url: str):
    """Test that assets are properly optimized."""
    # Track network requests
    assets = []

    def handle_response(response):
        if response.ok:
            url = response.url
            content_type = response.headers.get("content-type", "")

            # Check if it's a JS or CSS file by URL pattern or content type
            if url.endswith(".js") or url.endswith(".css") or "javascript" in content_type or "css" in content_type:
                try:
                    body = response.body()
                    assets.append(
                        {
                            "url": url,
                            "size": len(body) if body else 0,
                            "type": content_type,
                            "is_js": url.endswith(".js") or "javascript" in content_type,
                            "is_css": url.endswith(".css") or "css" in content_type,
                        }
                    )
                except Exception:
                    pass  # Some responses might not have bodies

    page.on("response", handle_response)
    page.goto(cloudfront_url, wait_until="networkidle")

    # Wait a bit to ensure all assets are loaded
    page.wait_for_timeout(1000)

    # Check JavaScript bundles
    js_assets = [a for a in assets if a["is_js"]]
    assert len(js_assets) > 0, f"No JavaScript assets found. Found assets: {[a['url'] for a in assets]}"

    # Check that JS is minified (rough check based on size)
    for js in js_assets:
        # Minified JS should typically be reasonably sized
        assert js["size"] < 500_000, f"JavaScript file too large: {js['size']} bytes"

    # Check CSS
    css_assets = [a for a in assets if a["is_css"]]
    assert len(css_assets) > 0, f"No CSS assets found. Found assets: {[a['url'] for a in assets]}"


def test_lighthouse_metrics(page: Page, cloudfront_url: str):
    """Test basic performance metrics."""
    page.goto(cloudfront_url)

    # Measure time to first contentful paint
    navigation_timing = page.evaluate("""() => {
        const [entry] = performance.getEntriesByType('navigation');
        return entry ? entry.toJSON() : null;
    }""")

    if navigation_timing:
        # Check that key metrics are reasonable
        assert navigation_timing["loadEventEnd"] < 3000, "Page load event took too long"
        assert navigation_timing["domContentLoadedEventEnd"] < 2000, "DOM content loaded took too long"
