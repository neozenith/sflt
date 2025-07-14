# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AWS CDK Python project that deploys a static React website to CloudFront with S3 as the origin, using Origin Access Control (OAC) for secure access. The React SPA is to leverage AWS Cognito federated with Google Identity auth using the PKCE OAuth flow.

There will be no backend other than S3, CloudFront, Lambda@Edge.

The authentication storage will be in browser cookies storing the JWT token.

The goal being that the webapp will be a frontend to manage the logged in user's Google Calendar which we will get permission from when they SSO sign in.

## Technology Stack

- **Infrastructure**: AWS CDK (Python)
- **Python**: 3.12+ with `uv` for dependency management
- **Frontend**: React with Vite
- **Build System**: Makefile
- **Deployment**: CloudFront + S3 with OAC

## Common Development Commands

```bash
# Install all dependencies (Python and frontend)
make install

# Build everything (frontend and CDK)
make build

# Deploy to AWS
make deploy

# Run CDK diff to see changes
make diff

# Destroy the stack
make destroy

# Run tests
make test

# Run e2e tests against deployed CloudFront
make test-e2e

# Run e2e tests against local dev server
make test-e2e-local

# Run linters
make lint

# Format code
make format

# Bootstrap CDK (first time only)
make bootstrap
```

## Architecture Overview

### Directory Structure
```
sflt/
├── app.py                 # CDK app entry point
├── cdk/                   # CDK infrastructure code
│   └── static_site_stack.py  # CloudFront + S3 stack definition
├── frontend/              # React application
│   ├── src/              # React source code
│   ├── public/           # Static assets
│   └── build/            # Build output (gitignored)
├── tests/                # Python unit tests
├── e2e/                  # Playwright end-to-end tests
│   ├── tests/           # E2E test files
│   └── conftest.py      # Pytest configuration for E2E
├── Makefile              # Build orchestration
└── cdk.json             # CDK configuration
```

### Infrastructure Architecture

The CDK stack (`StaticSiteStack`) creates:
1. **S3 Bucket**: Private bucket with encryption and versioning
2. **CloudFront Distribution**: 
   - Uses Origin Access Control (OAC) for secure S3 access
   - HTTPS redirect enabled
   - Caching optimized
   - Custom error pages for SPA routing
   - Lambda@Edge function for route protection
3. **Lambda@Edge Function**: Protects specific routes (returns 403 for unauthorized access)
4. **Bucket Deployment**: Automatically deploys frontend build to S3

### Key Design Decisions

1. **Origin Access Control (OAC)**: Using the latest OAC method instead of OAI for CloudFront-S3 integration
2. **Lambda@Edge**: Route protection at CloudFront edge locations for low latency
3. **Vite**: Modern, fast build tool for React development
4. **uv**: Fast Python package manager from Astral
5. **Error Handling**: 403/404 errors redirect to index.html for SPA routing (except protected routes)

## Protected Routes

The application includes Lambda@Edge route protection for authentication-required pages.

### Protected Paths

The following routes are protected and return 403 Forbidden:
- `/admin` - Admin dashboard
- `/dashboard` - User dashboard  
- `/profile` - User profile
- `/api/protected` - Protected API endpoints
- `/settings` - Application settings

### Public Paths

These routes remain publicly accessible:
- `/` - Homepage
- `/public` - Public information page

### Customizing Protected Routes

To modify protected routes, edit `cdk/lambda-edge/auth_handler.py` and update the `PROTECTED_ROUTES` list. After changes, redeploy with `make deploy`.

### Future Authentication

The Lambda@Edge function is designed to be extended with actual authentication logic. Currently, it returns 403 for all protected routes, but can be enhanced to:
- Check authentication tokens
- Validate session cookies
- Integrate with identity providers
- Implement role-based access control

## Development Workflow

1. Frontend development: `cd frontend && npm run dev`
2. Make changes to React app in `frontend/src/`
3. Build and deploy: `make deploy`
4. View CloudFront URL in CDK outputs

## E2E Testing

The project includes Playwright end-to-end tests to verify the deployed CloudFront distribution is working correctly.

### Running E2E Tests

```bash
# Test against deployed CloudFront distribution
make test-e2e

# Test against local development server
make test-e2e-local

# Run tests in headed mode (visible browser)
make test-e2e HEADED=true
```

### E2E Test Coverage

The e2e tests verify:
- Homepage loads correctly with expected content
- React counter functionality works
- Responsive design across different viewports
- CloudFront headers and caching
- SPA routing (404/403 redirects to index.html)
- Performance metrics and asset optimization
- Protected routes return 403 Forbidden
- Lambda@Edge route protection works correctly
- Navigation between public and protected routes

### Adding New E2E Tests

Create new test files in `e2e/tests/` following the pattern `test_*.py`. The tests automatically discover the CloudFront URL from AWS CloudFormation stack outputs.

## Important Notes

- Always use `uv` for Python dependency management
- Frontend build output goes to `frontend/build/` (configured in vite.config.js)
- The S3 bucket blocks all public access - access is only through CloudFront
- Remember to run `make bootstrap` before first deployment
- E2E tests require Playwright browsers to be installed (done automatically with `make install`)
- **AWS Profile**: Must export `AWS_PROFILE=sflt` before deployment commands
- **Check TODO.md for current open issues and blockers**

## Authentication Configuration & Bootstrapping

### The Circular Dependency Problem

This project has a circular dependency between the frontend configuration and CDK deployment:
1. Frontend needs to know the CloudFront domain for OAuth redirects
2. CloudFront domain is only known after CDK deployment
3. CDK deploys the frontend build, which needs the configuration

### Solution: Auto-Convergence

The project implements an auto-convergence pattern to handle this:

1. **First Deployment**: Use `make deploy-converge`
   - Deploys with placeholder configuration
   - Generates correct `aws-exports.js` from stack outputs
   - Automatically rebuilds frontend if configuration changed
   - Redeploys with correct configuration

2. **Subsequent Deployments**: 
   - `make deploy` - Standard deployment
   - `make deploy-converge` - Deployment with automatic configuration drift detection and correction

### Manual Configuration Update

If needed, you can manually regenerate the configuration:
```bash
make generate-aws-exports  # Generate aws-exports.js from current stack outputs
make build                 # Rebuild frontend with new configuration
make deploy               # Deploy updated frontend
```

### Configuration Drift Detection

The system automatically detects configuration drift by comparing:
- User Pool ID from Auth Stack
- User Pool Client ID from Auth Stack  
- CloudFront domain from Static Site Stack

If any values differ from what's in `frontend/src/aws-exports.js`, the system will automatically converge.

## Coding Standards

### Repository Hygiene

1. **Keep repository root clean**
   - No temporary files in the root directory
   - All temporary/generated files go in `tmp/` (which is gitignored)
   - Use `make clean` to clean up temporary files

2. **Temporary File Organization**
   - `tmp/test-artifacts/` - Test outputs, logs, temporary test data
   - `tmp/lambda-analysis/` - Downloaded Lambda code for analysis
   - `tmp/screenshots/` - Playwright test screenshots
   - `tmp/build-artifacts/` - Temporary build outputs

3. **Write Tests, Not Scripts**
   - Always prefer writing proper tests over one-off terminal scripts
   - If you need test data, add it to the test suite
   - E2E tests go in `frontend/e2e/`
   - Unit tests go in `frontend/src/test/`
   - Python tests go in `tests/`

4. **Code Quality**
   - Run linting before committing: `make lint`
   - Format code regularly: `make format`
   - Always orient to repo root: `cd $(git rev-parse --show-toplevel)`

5. **Documentation**
   - Update this file with important project changes
   - Document infrastructure changes in code comments
   - Keep README.md updated for users

6. **Scripts Directory**
   - All scripts must be PEP-723 compliant with inline dependencies
   - Execute scripts using `uv run scripts/script_name.py`
   - See `scripts/CLAUDE.md` for detailed guidelines

7. **Template System**
   - Lambda@Edge code is generated from `auth_handler.py.template`
   - Frontend config is generated from CDK stack outputs
   - Use `make generate-lambda-code` and `make generate-aws-exports`

## Claude's Working Notes

### Current Infrastructure Status (2025-07-10)

- **CloudFront Distribution**: `d3nteozhns257o.cloudfront.net`
- **Cognito User Pool**: `ap-southeast-2_u6zH1Pbty`
- **Cognito Client ID**: `2chnp95qkugngcet88uiokikpm` (PKCE-enabled)
- **Lambda@Edge Function**: `SfltAuthLambdaEdgeV6` (in us-east-1)
- **Authentication**: Cognito with Google OAuth integration using PKCE flow

### Recent Work

- Implemented Cognito authentication with Google OAuth
- Added PKCE support for secure SPA authentication
- Created Lambda@Edge function for JWT validation and smart redirects
- Fixed OAuth flow issues with proper client ID configuration
- Added comprehensive Playwright E2E tests for authentication flow
- Implemented auto-convergence pattern to handle circular dependency between CDK and frontend configuration
- Created `scripts/generate_aws_exports.py` to dynamically generate frontend config from stack outputs
- Modified Lambda@Edge to return 401 instead of redirecting, enabling client-side PKCE flow
- Added `make deploy-converge` command for automatic configuration drift detection and correction