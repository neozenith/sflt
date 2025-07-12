"""Lambda@Edge function for protecting routes with JWT validation."""

import base64
import json
import urllib.parse
from typing import Any

# Define protected route patterns
PROTECTED_ROUTES = [
    "/admin",
    "/dashboard",
    "/profile",
    "/api/protected",
    "/settings",
]

# Cognito configuration - injected by CDK at deployment time
COGNITO_DOMAIN = "sflt-auth.auth.ap-southeast-2.amazoncognito.com"
COGNITO_CLIENT_ID = "2chnp95qkugngcet88uiokikpm"
COGNITO_REGION = "ap-southeast-2"
USER_POOL_ID = "ap-southeast-2_u6zH1Pbty"


def is_protected_route(uri: str) -> bool:
    """Check if the requested URI is a protected route."""
    # Normalize the URI
    uri = uri.rstrip("/")

    # Check exact matches and prefix matches
    for route in PROTECTED_ROUTES:
        if uri == route or uri.startswith(f"{route}/"):
            return True
    return False


def parse_jwt_payload(token: str) -> dict[str, Any] | None:
    """
    Parse JWT payload without verification (for basic validation only).
    In production, you should verify the JWT signature.
    """
    try:
        # JWT has 3 parts: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode the payload (second part)
        payload = parts[1]
        # Add padding if needed
        payload += "=" * (-len(payload) % 4)
        decoded_bytes = base64.urlsafe_b64decode(payload)
        payload_dict = json.loads(decoded_bytes.decode("utf-8"))

        return payload_dict
    except Exception as e:
        print(f"Error parsing JWT: {str(e)}")
        return None


def is_jwt_valid(payload: dict[str, Any]) -> bool:
    """
    Basic JWT validation (expiration, issuer, audience).
    In production, you should also verify the signature.
    """
    import time

    try:
        # Check expiration
        exp = payload.get("exp")
        if not exp or exp < time.time():
            print("JWT expired or no expiration")
            return False

        # Check issuer - now uses templated values
        iss = payload.get("iss")
        expected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}"
        if iss != expected_issuer:
            print(f"Invalid issuer: {iss}")
            return False

        # Check audience (client_id)
        aud = payload.get("aud")
        if aud != COGNITO_CLIENT_ID:
            print(f"Invalid audience: {aud}")
            return False

        # Check token use (should be 'id' for ID tokens)
        token_use = payload.get("token_use")
        if token_use != "id":
            print(f"Invalid token use: {token_use}")
            return False

        return True
    except Exception as e:
        print(f"Error validating JWT: {str(e)}")
        return False


def extract_token_from_cookie(cookie_header: str) -> str | None:
    """Extract the ID token from cookies."""
    try:
        cookies = {}
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                key, value = cookie.strip().split("=", 1)
                cookies[key] = value

        # Look for common Cognito token cookie names
        for token_key in [
            "CognitoIdentityServiceProvider." + COGNITO_CLIENT_ID + ".LastAuthUser.idToken",
            "amplify-signin-with-hostedui",
            "id_token",
        ]:
            if token_key in cookies:
                return cookies[token_key]

        return None
    except Exception as e:
        print(f"Error extracting token from cookie: {str(e)}")
        return None


def create_login_redirect(original_uri: str, host: str) -> dict[str, Any]:
    """Create a redirect response to Cognito login with target URL preservation."""
    # Encode the target URL to redirect back to after login
    encoded_redirect_uri = urllib.parse.quote(f"https://{host}/", safe="")
    state_param = urllib.parse.quote(json.dumps({"target": original_uri}), safe="")

    # Fixed: Use /login endpoint instead of /oauth2/authorize for hosted UI
    login_url = (
        f"https://{COGNITO_DOMAIN}/login?"
        f"client_id={COGNITO_CLIENT_ID}&"
        f"response_type=code&"
        f"scope=email+openid+profile&"
        f"redirect_uri={encoded_redirect_uri}&"
        f"state={state_param}"
    )

    return {
        "status": "302",
        "statusDescription": "Found",
        "headers": {
            "location": [{"key": "Location", "value": login_url}],
            "cache-control": [{"key": "Cache-Control", "value": "no-cache, no-store, must-revalidate"}],
        },
    }


def handler(event, context):
    """
    Lambda@Edge handler for viewer request events.
    Validates JWT tokens for protected routes and redirects to login if needed.
    Also handles SPA routing by rewriting non-file paths to index.html.
    """
    try:
        request = event["Records"][0]["cf"]["request"]
        uri = request["uri"]
        headers = request.get("headers", {})

        # Add some basic logging (limited in Lambda@Edge)
        print(f"Processing request for URI: {uri}")

        # Check if this is an OAuth callback (has authorization code)
        querystring = request.get("querystring", "")
        if uri == "/" and "code=" in querystring:
            print(f"OAuth callback detected with code parameter, serving React app")
            request["uri"] = "/index.html"
            return request

        # Check if this is a protected route
        if is_protected_route(uri):
            print(f"URI {uri} is protected, checking authentication")

            # Extract JWT token from cookies
            token = None
            if "cookie" in headers:
                cookie_header = headers["cookie"][0]["value"]
                token = extract_token_from_cookie(cookie_header)

            # If no token found, redirect to OAuth login
            if not token:
                print(f"No token found for protected route {uri}, redirecting to OAuth login")
                host = headers.get("host", [{}])[0].get("value", "")
                return create_login_redirect(uri, host)

            # Parse and validate JWT
            payload = parse_jwt_payload(token)
            if not payload or not is_jwt_valid(payload):
                print(f"Invalid or expired token for {uri}, redirecting to OAuth login")
                host = headers.get("host", [{}])[0].get("value", "")
                return create_login_redirect(uri, host)

            # Token is valid, log user info and serve React app
            user_email = payload.get("email", "unknown")
            print(f"Valid token for user {user_email} accessing {uri}, serving React app")

            # Add user info to request headers for downstream use
            request["headers"]["x-authenticated-user"] = [{"key": "X-Authenticated-User", "value": user_email}]
            request["headers"]["x-lambda-edge"] = [{"key": "X-Lambda-Edge", "value": "authenticated"}]

            # Serve React app for protected routes (SPA will handle client-side routing)
            request["uri"] = "/index.html"
            return request

        # For SPA routing: if the path doesn't have a file extension and isn't the root,
        # it's likely a React route that should serve index.html
        if uri != "/" and "." not in uri.split("/")[-1]:
            print(f"URI {uri} looks like a SPA route, rewriting to /index.html")
            request["uri"] = "/index.html"

        print(f"URI {uri} processing complete, passing through")
        # For non-protected routes or authenticated protected routes, pass through the request
        return request
    except Exception as e:
        print(f"Error in Lambda@Edge function: {str(e)}")
        # In case of error, pass through the request
        return event["Records"][0]["cf"]["request"]