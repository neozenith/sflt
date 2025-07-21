# Feature Branch Deployment Usage Guide

This guide demonstrates how to use the new feature branch isolation system for the SFLT project.

## Quick Start

### 1. Deploy a Feature Branch

```bash
# Create a new feature branch
git checkout -b feature/calendar-integration

# Deploy the feature branch (automatically gets isolated stack names)
export AWS_PROFILE=sflt
make deploy-feature

# Generated stack names:
# - sflt-feature-calendar-integration-auth (ap-southeast-2)
# - sflt-feature-calendar-integration-site (us-east-1)
```

### 2. Generate Configuration for Feature Branch

```bash
# Generate aws-exports.js for your feature branch
make generate-aws-exports-feature

# Generate Lambda@Edge code for your feature branch
make generate-lambda-code-feature
```

### 3. List All Feature Branch Stacks

```bash
# See all feature branch deployments across both regions
make list-feature-stacks
```

### 4. Clean Up When Done

```bash
# Destroy your feature branch stacks
make destroy-feature

# Or clean up old/merged branches automatically
make cleanup-feature-branches
```

## Parallel Development Example

```bash
# Developer 1 - Working on authentication improvements
git checkout -b feature/auth-enhancement
export AWS_PROFILE=sflt
make deploy-feature
# Stacks: sflt-feature-auth-enhancement-auth, sflt-feature-auth-enhancement-site

# Developer 2 - Working on UI improvements (simultaneously)
git checkout -b feature/ui-improvements  
export AWS_PROFILE=sflt
make deploy-feature
# Stacks: sflt-feature-ui-improvements-auth, sflt-feature-ui-improvements-site

# No conflicts! Each developer has completely isolated infrastructure
```

## Stack Naming Convention

The system automatically generates stack names based on your git branch:

| Branch Name | Auth Stack Name | Static Site Stack Name |
|-------------|-----------------|------------------------|
| `main` | `sflt-main-auth` | `sflt-main-site` |
| `develop` | `sflt-develop-auth` | `sflt-develop-site` |
| `feature/calendar-integration` | `sflt-feature-calendar-integration-auth` | `sflt-feature-calendar-integration-site` |
| `fix/oauth-bug` | `sflt-fix-oauth-bug-auth` | `sflt-fix-oauth-bug-site` |

## Resource Naming

All AWS resources get branch-specific prefixes:

| Resource Type | Example Name |
|---------------|--------------|
| Cognito User Pool | `sflt-feature-calendar-integration-user-pool` |
| Lambda@Edge Function | `sflt-feature-calendar-integration-auth-edge` |
| S3 Bucket | `sflt-feature-calendar-integration-website-{account}` |
| Secrets Manager | `sflt-feature-calendar-integration-google-oauth` |

## Environment-Specific Behavior

### Feature Branches (`feature/*`, `fix/*`)
- **Removal Policy**: DESTROY (automatic cleanup)
- **Auto-delete S3 objects**: Yes
- **Tags**: `AutoCleanup=true`, `FeatureBranch={branch-name}`

### Production Branches (`main`)
- **Removal Policy**: RETAIN (safe from accidental deletion)
- **Auto-delete S3 objects**: No
- **Tags**: `Environment=prod`

### Staging Branches (`develop`)
- **Removal Policy**: RETAIN 
- **Auto-delete S3 objects**: No
- **Tags**: `Environment=staging`

## Configuration Drift Detection

The system automatically detects when your frontend configuration is out of sync with deployed infrastructure:

```bash
# If your aws-exports.js doesn't match deployed stacks, you'll see:
make generate-aws-exports-feature

# Output:
# ⚠️  User Pool ID drift: old_id → new_id
# ⚠️  CloudFront domain drift: old_domain → new_domain
# ✅ Configuration updated to match stack outputs
```

## Cross-Region Support

The system maintains the same cross-region architecture as the original:
- **Auth Stack**: Your preferred region (default: ap-southeast-2)
- **Static Site Stack**: us-east-1 (required for Lambda@Edge)
- **Cross-region references**: Automatically managed with environment-specific export names

## Enhanced Cleanup System

The enhanced cleanup system handles both regular old stacks and Lambda@Edge blocked stacks:

### Regular Cleanup (7+ Days Old)
```bash
make cleanup-feature-branches

# Criteria for deletion:
# - Stack is older than 7 days
# - Branch no longer exists in git remotes
# - Stack name starts with 'sflt-' (but not main/develop)
# - Stack is in a stable state (CREATE_COMPLETE, UPDATE_COMPLETE, etc.)
```

### Lambda@Edge Cleanup (24+ Hours After Failure)
```bash
# List Lambda@Edge blocked stacks
make list-blocked-stacks

# Retry cleanup of Lambda@Edge blocked stacks (after 24-48h)
make cleanup-lambda-edge

# Comprehensive cleanup (old stacks + Lambda@Edge retries)
make cleanup-all
```

### Enhanced Destroy Process
```bash
# Enhanced destroy with Lambda@Edge handling
make destroy-retry

# This will:
# 1. Detect Lambda@Edge functions automatically
# 2. Attempt individual stack destruction with proper timeouts
# 3. Create cleanup reminder scripts for blocked stacks
# 4. Exit with appropriate status codes
```

## Monitoring and Troubleshooting

### View Stack Status
```bash
# List all feature branch stacks with status
make list-feature-stacks

# Get outputs for your current branch
make generate-aws-exports-feature
```

### Debug Stack Issues
```bash
# Check what stacks would be created/updated
uv run cdk diff --all

# View current configuration
export GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Branch: $GIT_BRANCH"
echo "Stack prefix: sflt-$(echo $GIT_BRANCH | tr '/' '-' | tr '_' '-' | tr '[:upper:]' '[:lower:]')"
```

## Integration with Existing Workflows

The feature branch system is fully backward compatible:

- `make deploy` still works for main branch deployments
- `make generate-aws-exports` still works for original stack names
- All existing scripts and tooling continue to function

## Best Practices

### 1. Always Use Feature Branches
```bash
# ✅ Good
git checkout -b feature/new-functionality
make deploy-feature

# ❌ Avoid - deploys to shared main infrastructure
git checkout main
make deploy
```

### 2. Clean Up Regularly
```bash
# Run weekly to clean up old feature branches
make cleanup-feature-branches
```

### 3. Use Consistent Branch Naming
```bash
# ✅ Good branch names (clean stack names)
feature/calendar-integration
fix/oauth-bug
enhancement/ui-improvements

# ⚠️ Acceptable but verbose
feature/SFLT-123-add-calendar-integration

# ❌ Avoid special characters
feature/calendar@integration  # @ becomes -
feature/calendar_integration  # _ becomes -
```

### 4. Monitor Costs
Use AWS Cost Explorer with these filters:
- Tag: `Project = sflt`
- Tag: `AutoCleanup = true` (for feature branch resources)

## Migration from Legacy System

If you have existing `SfltAuthStack` and `SfltStaticSiteStack` deployments:

1. **They continue to work unchanged** - no breaking changes
2. **To migrate to new system**:
   ```bash
   # Deploy main branch with new naming
   git checkout main
   export GIT_BRANCH=main
   make deploy-feature  # Creates sflt-main-auth and sflt-main-site
   
   # After validation, destroy old stacks
   uv run cdk destroy SfltAuthStack SfltStaticSiteStack
   ```

## Troubleshooting

### "Stack already exists" Error
```bash
# If you get conflicts, check for existing stacks
make list-feature-stacks

# Clean up conflicting stacks
make destroy-feature
```

### "Export not found" Error
```bash
# Cross-region export issues - ensure auth stack deployed first
uv run cdk deploy sflt-{branch-name}-auth --region ap-southeast-2
uv run cdk deploy sflt-{branch-name}-site --region us-east-1
```

### Lambda@Edge Cleanup Issues
```bash
# Lambda@Edge functions cannot be deleted immediately due to global replication
# Error: "Lambda was unable to delete because it is a replicated function"

# Solution 1: Wait 24-48 hours, then retry
make destroy-retry

# Solution 2: Use cleanup reminder script (created automatically)
./tmp/cleanup_reminder_feature_branch_name.sh

# Solution 3: Manual AWS Console deletion after replication expires
```

### Configuration Drift
```bash
# If aws-exports.js is out of sync
make generate-aws-exports-feature

# If Lambda@Edge code is out of sync  
make generate-lambda-code-feature
```

## Lambda@Edge Cleanup Guide

### Understanding Lambda@Edge Limitations

**Why Lambda@Edge Functions Can't Be Deleted Immediately:**
- Lambda@Edge functions are replicated to all AWS edge locations globally
- AWS requires 24-48 hours for replicas to expire before allowing deletion
- This is a limitation of the AWS service, not our cleanup system

**Exit Codes:**
- `0` - Complete cleanup success
- `1` - Cleanup failed
- `2` - Partial success (auth stack deleted, site stack blocked by Lambda@Edge)

### Cleanup Workflow

**1. Initial Cleanup Attempt:**
```bash
make destroy
# or  
make destroy-retry  # Enhanced version with better handling
```

**2. Check Blocked Stacks:**
```bash
make list-blocked-stacks
# Shows which stacks are blocked and when they'll be ready for retry
```

**3. Retry After 24-48 Hours:**
```bash
# Option A: Use reminder script (created automatically)
./tmp/cleanup_reminder_feature_my_branch.sh

# Option B: Manual retry
make cleanup-lambda-edge

# Option C: Comprehensive cleanup
make cleanup-all
```

**4. Monitor Progress:**
```bash
make list-feature-stacks
# Should show DELETE_COMPLETE or no results when finished
```