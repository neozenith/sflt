# TODO - Open Issues

## Critical Issues

### 1. AWS Profile Not Set ✅ FIXED
- **Issue**: Production deployment fails due to missing AWS profile
- **Error**: `Unable to locate credentials. You can configure credentials by running "aws configure"`
- **Impact**: Cannot deploy to production
- **Solution**: ✅ Export AWS profile before deployment: `export AWS_PROFILE=sflt`

### 2. Node.js Version Compatibility Warning
- **Issue**: CDK shows warnings about unsupported Node.js version (v23.11.0)
- **Warning**: "This software has not been tested with node v23.11.0"
- **Impact**: May cause runtime issues during deployment
- **Solution**: Use supported Node.js versions (^20.0.0 or ^22.0.0) or set `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION` environment variable

### 3. CDK Stack Deployment Strategy ✅ FIXED
- **Issue**: Deployment fails when not specifying which stack to deploy
- **Error**: "Since this app includes more than a single stack, specify which stacks to use"
- **Impact**: `make deploy` command fails
- **Solution**: ✅ Updated Makefile to deploy all stacks with `--all` flag

### 4. Lambda@Edge Stack Dependency Issue
- **Issue**: CDK stack deployment fails due to cross-region export conflicts
- **Error**: `Exports cannot be updated: /cdk/exports/SfltStaticSiteStack/SfltLambdaEdgeStackV4useast1RefAuthLambdaCurrentVersion... is in use by stack(s) SfltStaticSiteStack`
- **Impact**: Blocks deployment updates to Lambda@Edge function
- **Solution**: May need to deploy stacks in specific order or temporarily remove dependencies

## Working Status Summary

### ✅ Working
- **Local Development**: Frontend dev server starts successfully on port 5174
- **Build Process**: Frontend builds without errors
- **Tests**: All unit tests pass (3/3)
- **Linting**: All linters pass with no errors
- **Code Quality**: Ruff and ESLint checks pass

### ❌ Blocked
- **Lambda@Edge Stack Updates**: Blocked by cross-region export conflicts
- **Full Stack Deployment**: Partially successful (Auth stack deployed, Lambda@Edge failed)

## Next Steps

1. **Immediate**: Resolve Lambda@Edge stack dependency issue
2. **Short-term**: Consider Node.js version downgrade for better compatibility
3. **Optional**: Silence Node.js version warnings with environment variable

## Lambda@Edge Warning

- **Issue**: CDK shows warning about Lambda authorization strategy changes
- **Warning**: "AWS Lambda has changed their authorization strategy"
- **Impact**: May cause client invocations to fail with Access Denied errors
- **Status**: Monitoring - may need to update Lambda permissions if issues occur


- https://github.com/authts/oidc-client-ts/blob/main/docs/protocols/authorization-code-grant-with-pkce.md
- https://github.com/authts/react-oidc-context