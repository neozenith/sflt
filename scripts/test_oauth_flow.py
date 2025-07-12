#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests",
# ]
# ///
"""Test the complete OAuth flow end-to-end."""

import sys
import urllib.parse
from pathlib import Path

import requests


# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")


def test_protected_route_redirect():
    """Test that protected routes redirect to OAuth login."""
    print_header("Testing Protected Route Redirect")
    
    base_url = "https://d3nteozhns257o.cloudfront.net"
    protected_routes = ["/admin", "/dashboard", "/profile"]
    
    for route in protected_routes:
        print_info(f"Testing protected route: {route}")
        
        try:
            response = requests.get(f"{base_url}{route}", allow_redirects=False)
            
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                
                if 'sflt-auth.auth.ap-southeast-2.amazoncognito.com/login' in location:
                    print_success(f"✅ {route} correctly redirects to OAuth login")
                    
                    # Parse redirect URL
                    parsed_url = urllib.parse.urlparse(location)
                    params = urllib.parse.parse_qs(parsed_url.query)
                    
                    # Check required OAuth parameters
                    required_params = ['client_id', 'response_type', 'scope', 'redirect_uri', 'state']
                    for param in required_params:
                        if param in params:
                            print_success(f"  ✓ {param}: {params[param][0][:50]}...")
                        else:
                            print_error(f"  ✗ Missing required parameter: {param}")
                    
                    # Check state parameter contains target
                    if 'state' in params:
                        try:
                            state_data = urllib.parse.unquote(params['state'][0])
                            if route in state_data:
                                print_success(f"  ✓ State parameter contains target route: {route}")
                            else:
                                print_warning(f"  ⚠ State parameter doesn't contain target route")
                        except Exception as e:
                            print_error(f"  ✗ Error parsing state parameter: {e}")
                    
                else:
                    print_error(f"✗ {route} redirects to wrong URL: {location}")
            else:
                print_error(f"✗ {route} returns {response.status_code}, expected 302")
                
        except Exception as e:
            print_error(f"✗ Error testing {route}: {e}")


def test_oauth_callback_handling():
    """Test that OAuth callback is handled correctly."""
    print_header("Testing OAuth Callback Handling")
    
    base_url = "https://d3nteozhns257o.cloudfront.net"
    
    # Test OAuth callback URL (simulates what Cognito would redirect to)
    callback_url = f"{base_url}/?code=test_code&state=%7B%22target%22%3A%20%22%2Fadmin%22%7D"
    
    print_info(f"Testing OAuth callback: {callback_url}")
    
    try:
        response = requests.get(callback_url, allow_redirects=False)
        
        if response.status_code == 200:
            print_success("✅ OAuth callback serves React app (200 OK)")
            
            # Check that it's serving the React app
            if 'text/html' in response.headers.get('Content-Type', ''):
                print_success("  ✓ Response is HTML (React app)")
            else:
                print_warning("  ⚠ Response is not HTML")
                
            # Check for React app indicators
            content = response.text
            if 'id="root"' in content:
                print_success("  ✓ HTML contains React root element")
            else:
                print_warning("  ⚠ HTML doesn't contain React root element")
                
        else:
            print_error(f"✗ OAuth callback returns {response.status_code}, expected 200")
            
    except Exception as e:
        print_error(f"✗ Error testing OAuth callback: {e}")


def test_public_routes():
    """Test that public routes work correctly."""
    print_header("Testing Public Routes")
    
    base_url = "https://d3nteozhns257o.cloudfront.net"
    public_routes = ["/", "/public"]
    
    for route in public_routes:
        print_info(f"Testing public route: {route}")
        
        try:
            response = requests.get(f"{base_url}{route}")
            
            if response.status_code == 200:
                print_success(f"✅ {route} accessible (200 OK)")
                
                # Check that it's serving the React app
                if 'text/html' in response.headers.get('Content-Type', ''):
                    print_success(f"  ✓ Response is HTML (React app)")
                else:
                    print_warning(f"  ⚠ Response is not HTML")
                    
            else:
                print_error(f"✗ {route} returns {response.status_code}, expected 200")
                
        except Exception as e:
            print_error(f"✗ Error testing {route}: {e}")


def test_spa_routing():
    """Test that SPA routes serve the React app."""
    print_header("Testing SPA Routing")
    
    base_url = "https://d3nteozhns257o.cloudfront.net"
    spa_routes = ["/nonexistent", "/some/nested/route"]
    
    for route in spa_routes:
        print_info(f"Testing SPA route: {route}")
        
        try:
            response = requests.get(f"{base_url}{route}")
            
            if response.status_code == 200:
                print_success(f"✅ {route} serves React app (200 OK)")
                
                # Check that it's serving the React app
                if 'text/html' in response.headers.get('Content-Type', ''):
                    print_success(f"  ✓ Response is HTML (React app)")
                else:
                    print_warning(f"  ⚠ Response is not HTML")
                    
            else:
                print_error(f"✗ {route} returns {response.status_code}, expected 200")
                
        except Exception as e:
            print_error(f"✗ Error testing {route}: {e}")


def test_static_assets():
    """Test that static assets are served correctly."""
    print_header("Testing Static Assets")
    
    base_url = "https://d3nteozhns257o.cloudfront.net"
    
    # Test CSS and JS assets
    try:
        # Get the main HTML page first to find asset paths
        response = requests.get(base_url)
        if response.status_code == 200:
            content = response.text
            
            # Look for CSS and JS references
            import re
            css_matches = re.findall(r'href="([^"]*\.css)"', content)
            js_matches = re.findall(r'src="([^"]*\.js)"', content)
            
            for css_file in css_matches:
                asset_url = f"{base_url}{css_file}"
                print_info(f"Testing CSS asset: {css_file}")
                
                asset_response = requests.get(asset_url)
                if asset_response.status_code == 200:
                    print_success(f"  ✓ CSS asset accessible")
                else:
                    print_error(f"  ✗ CSS asset returns {asset_response.status_code}")
            
            for js_file in js_matches:
                asset_url = f"{base_url}{js_file}"
                print_info(f"Testing JS asset: {js_file}")
                
                asset_response = requests.get(asset_url)
                if asset_response.status_code == 200:
                    print_success(f"  ✓ JS asset accessible")
                else:
                    print_error(f"  ✗ JS asset returns {asset_response.status_code}")
                    
        else:
            print_error(f"✗ Could not get main page to find assets")
            
    except Exception as e:
        print_error(f"✗ Error testing static assets: {e}")


def main():
    """Run all OAuth flow tests."""
    print_header("OAuth Flow End-to-End Tests")
    
    print("Testing the complete OAuth PKCE flow implementation...")
    print("This verifies that Lambda@Edge and React app work together correctly.")
    
    # Run all tests
    test_protected_route_redirect()
    test_oauth_callback_handling()
    test_public_routes()
    test_spa_routing()
    test_static_assets()
    
    print_header("Test Summary")
    print("✅ OAuth flow tests completed!")
    print("🌐 Test the full flow manually:")
    print("   1. Visit: https://d3nteozhns257o.cloudfront.net/admin")
    print("   2. Should redirect to Google OAuth")
    print("   3. After login, should return to /admin")
    print("   4. React app should handle the OAuth callback")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())