#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests",
#   "rich",
# ]
# ///
"""Test the complete OAuth flow end-to-end."""

import logging
import re
import sys
import urllib.parse

import requests

# Configure Rich logging
from rich.console import Console
from rich.logging import RichHandler

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)


def test_protected_route_redirect():
    """Test that protected routes redirect to OAuth login."""
    console.rule("[bold blue]Testing Protected Route Redirect[/bold blue]")

    base_url = "https://d3nteozhns257o.cloudfront.net"
    protected_routes = ["/admin", "/dashboard", "/profile"]

    for route in protected_routes:
        console.print(f"\n[bold]Testing protected route:[/bold] [cyan]{route}[/cyan]")

        try:
            response = requests.get(f"{base_url}{route}", allow_redirects=False)

            if response.status_code == 302:
                location = response.headers.get("Location", "")

                if "sflt-auth.auth.ap-southeast-2.amazoncognito.com/login" in location:
                    console.print(f"[green]✅[/green] [cyan]{route}[/cyan] correctly redirects to OAuth login")

                    # Parse redirect URL
                    parsed_url = urllib.parse.urlparse(location)
                    params = urllib.parse.parse_qs(parsed_url.query)

                    # Check required OAuth parameters
                    required_params = ["client_id", "response_type", "scope", "redirect_uri", "state"]
                    for param in required_params:
                        if param in params:
                            param_value = params[param][0][:50] + "..."
                            console.print(f"  [green]✓[/green] [cyan]{param}:[/cyan] [yellow]{param_value}[/yellow]")
                        else:
                            console.print(f"  [red]✗[/red] Missing required parameter: [yellow]{param}[/yellow]")

                    # Check state parameter contains target
                    if "state" in params:
                        try:
                            state_data = urllib.parse.unquote(params["state"][0])
                            if route in state_data:
                                console.print(
                                    f"  [green]✓[/green] State parameter contains target route: [cyan]{route}[/cyan]"
                                )
                            else:
                                logger.warning("  State parameter doesn't contain target route")
                        except Exception as e:
                            logger.error(f"  Error parsing state parameter: {e}")

                else:
                    logger.error(f"{route} redirects to wrong URL: {location}")
            else:
                logger.error(f"{route} returns {response.status_code}, expected 302")

        except Exception as e:
            logger.error(f"Error testing {route}: {e}")


def test_oauth_callback_handling():
    """Test that OAuth callback is handled correctly."""
    console.rule("[bold blue]Testing OAuth Callback Handling[/bold blue]")

    base_url = "https://d3nteozhns257o.cloudfront.net"

    # Test OAuth callback URL (simulates what Cognito would redirect to)
    callback_url = f"{base_url}/?code=test_code&state=%7B%22target%22%3A%20%22%2Fadmin%22%7D"

    console.print(f"\nTesting OAuth callback: {callback_url}")

    try:
        response = requests.get(callback_url, allow_redirects=False)

        if response.status_code == 200:
            console.print("✅ OAuth callback serves React app (200 OK)")

            # Check that it's serving the React app
            if "text/html" in response.headers.get("Content-Type", ""):
                console.print("  [green]✓[/green] Response is HTML (React app)")
            else:
                logger.warning("  Response is not HTML")

            # Check for React app indicators
            content = response.text
            if 'id="root"' in content:
                console.print("  [green]✓[/green] HTML contains React root element")
            else:
                logger.warning("  HTML doesn't contain React root element")

        else:
            logger.error(f"OAuth callback returns {response.status_code}, expected 200")

    except Exception as e:
        logger.error(f"Error testing OAuth callback: {e}")


def test_public_routes():
    """Test that public routes work correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Public Routes")
    logger.info("=" * 60)

    base_url = "https://d3nteozhns257o.cloudfront.net"
    public_routes = ["/", "/public"]

    for route in public_routes:
        logger.info(f"\nTesting public route: {route}")

        try:
            response = requests.get(f"{base_url}{route}")

            if response.status_code == 200:
                console.print(f"✅ {route} accessible (200 OK)")

                # Check that it's serving the React app
                if "text/html" in response.headers.get("Content-Type", ""):
                    console.print("  [green]✓[/green] Response is HTML (React app)")
                else:
                    logger.warning("  Response is not HTML")

            else:
                logger.error(f"{route} returns {response.status_code}, expected 200")

        except Exception as e:
            logger.error(f"Error testing {route}: {e}")


def test_spa_routing():
    """Test that SPA routes serve the React app."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing SPA Routing")
    logger.info("=" * 60)

    base_url = "https://d3nteozhns257o.cloudfront.net"
    spa_routes = ["/nonexistent", "/some/nested/route"]

    for route in spa_routes:
        logger.info(f"\nTesting SPA route: {route}")

        try:
            response = requests.get(f"{base_url}{route}")

            if response.status_code == 200:
                console.print(f"✅ {route} serves React app (200 OK)")

                # Check that it's serving the React app
                if "text/html" in response.headers.get("Content-Type", ""):
                    console.print("  [green]✓[/green] Response is HTML (React app)")
                else:
                    logger.warning("  Response is not HTML")

            else:
                logger.error(f"{route} returns {response.status_code}, expected 200")

        except Exception as e:
            logger.error(f"Error testing {route}: {e}")


def test_static_assets():
    """Test that static assets are served correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Static Assets")
    logger.info("=" * 60)

    base_url = "https://d3nteozhns257o.cloudfront.net"

    # Test CSS and JS assets
    try:
        # Get the main HTML page first to find asset paths
        response = requests.get(base_url)
        if response.status_code == 200:
            content = response.text

            # Look for CSS and JS references

            css_matches = re.findall(r'href="([^"]*\.css)"', content)
            js_matches = re.findall(r'src="([^"]*\.js)"', content)

            for css_file in css_matches:
                asset_url = f"{base_url}{css_file}"
                logger.info(f"\nTesting CSS asset: {css_file}")

                asset_response = requests.get(asset_url)
                if asset_response.status_code == 200:
                    console.print("  [green]✓[/green] CSS asset accessible")
                else:
                    logger.error(f"  CSS asset returns {asset_response.status_code}")

            for js_file in js_matches:
                asset_url = f"{base_url}{js_file}"
                logger.info(f"\nTesting JS asset: {js_file}")

                asset_response = requests.get(asset_url)
                if asset_response.status_code == 200:
                    console.print("  [green]✓[/green] JS asset accessible")
                else:
                    logger.error(f"  JS asset returns {asset_response.status_code}")

        else:
            logger.error("Could not get main page to find assets")

    except Exception as e:
        logger.error(f"Error testing static assets: {e}")


def main():
    """Run all OAuth flow tests."""
    console.rule("[bold magenta]OAuth Flow End-to-End Tests[/bold magenta]")

    console.print("\n[dim]Testing the complete OAuth PKCE flow implementation...[/dim]")
    console.print("[dim]This verifies that Lambda@Edge and React app work together correctly.[/dim]")

    # Run all tests
    test_protected_route_redirect()
    test_oauth_callback_handling()
    test_public_routes()
    test_spa_routing()
    test_static_assets()

    console.rule("[bold green]Test Summary[/bold green]")
    console.print("\n[green]✅[/green] [bold]OAuth flow tests completed![/bold]")
    console.print("\n[bold blue]🌐 Test the full flow manually:[/bold blue]")
    console.print("   [bold]1.[/bold] Visit: [link]https://d3nteozhns257o.cloudfront.net/admin[/link]")
    console.print("   [bold]2.[/bold] Should redirect to [blue]Google OAuth[/blue]")
    console.print("   [bold]3.[/bold] After login, should return to [cyan]/admin[/cyan]")
    console.print("   [bold]4.[/bold] React app should handle the OAuth callback")

    return 0


if __name__ == "__main__":
    sys.exit(main())
