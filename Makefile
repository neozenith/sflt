.PHONY: help install install-frontend build build-frontend deploy synth diff destroy clean test test-e2e test-e2e-local test-console-errors dev lint format bootstrap outputs diagram generate-aws-exports generate-lambda-code generate-configs triage check-lambda-propagation list-feature-stacks cleanup-feature-branches

export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

# Get current branch for dynamic stack naming
BRANCH := $(shell git rev-parse --abbrev-ref HEAD)
STACK_PREFIX := sflt-$(shell echo $(BRANCH) | tr '/' '-' | tr '_' '-' | tr '[:upper:]' '[:lower:]')

help:
	@echo "Available commands:"
	@echo "  make install          - Install all dependencies (Python and frontend)"
	@echo "  make build            - Build frontend and synthesize CDK"
	@echo "  make deploy           - Deploy stack with automatic configuration convergence"
	@echo "  make destroy          - Destroy the current branch stack"
	@echo "  make test             - Run all tests"
	@echo "  make test-e2e         - Run e2e tests against CloudFront"
	@echo "  make test-e2e-local   - Run e2e tests against local dev server"
	@echo "  make test-console-errors - Run console error detection tests"
	@echo "  make dev              - Start local development server"
	@echo "  make lint             - Run linters"
	@echo "  make format           - Format code"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make outputs          - Show CDK stack outputs"
	@echo "  make diagram          - Generate architecture diagram"
	@echo "  make generate-configs - Generate aws-exports.js and Lambda code from stack outputs"
	@echo "  make triage           - Run deployment triage and status analysis"
	@echo "  make check-lambda-propagation - Check Lambda@Edge propagation status during 5-minute window"
	@echo ""
	@echo "Feature branch management:"
	@echo "  make list-feature-stacks     - List all deployed feature branch stacks"
	@echo "  make cleanup-feature-branches - Clean up old feature branch stacks (>7 days)"
	@echo "  make cleanup-lambda-edge     - Retry cleanup of Lambda@Edge blocked stacks"
	@echo "  make cleanup-all             - Comprehensive cleanup (old + Lambda@Edge)"
	@echo "  make list-blocked-stacks     - List Lambda@Edge blocked stacks"
	@echo "  make destroy-retry           - Enhanced destroy with Lambda@Edge handling"
	@echo ""
	@echo "Current branch: $(BRANCH)"
	@echo "Stack prefix: $(STACK_PREFIX)"
	@echo ""
	@echo "Scripts can also be run directly:"
	@echo "  uv run scripts/script_name.py"

setup-claude-mcp:
	claude mcp add playwright npx @playwright/mcp@latest
	claude mcp add context7 -- npx -y @upstash/context7-mcp
	claude mcp add aws-nx-mcp -- npx -y -p @aws/nx-plugin aws-nx-mcp
	claude mcp add sequential-thinking -- npx @modelcontextprotocol/server-sequential-thinking
	claude mcp add magicui -- npx @21st/mcp

setup-super-claude:
	uv add SuperClaude
	uv run SuperClaude install --profile developer -y

install:
	uv sync
	$(MAKE) install-frontend
	$(MAKE) install-playwright

install-frontend:
	cd frontend && npm install

# Build target no longer includes generate-lambda-code to avoid circular dependency
build: build-frontend synth

build-frontend:
	cd frontend && npm run build

synth:
	uv run cdk synth --all

diff:
	uv run cdk diff

# Unified deploy with automatic convergence for any branch
deploy: build
	@uv run scripts/deploy_orchestrator.py

destroy:
	@uv run scripts/destroy_orchestrator.py

clean:
	rm -rf cdk.out
	rm -rf frontend/build
	rm -rf tmp/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

test:
	uv run pytest tests/

lint:
	uv run ruff check .
	cd frontend && npm run lint

format:
	uv run ruff format .
	cd frontend && npm run format

bootstrap:
	uv run cdk bootstrap

test-e2e:
	@echo "Running e2e tests against CloudFront..."
	uv run python -m pytest e2e/tests/ -v $(if $(HEADED),--headed,)

test-e2e-local:
	@echo "Running e2e tests against local dev server..."
	E2E_BASE_URL=http://localhost:5173 uv run python -m pytest e2e/tests/ -v $(if $(HEADED),--headed,)

test-console-errors:
	@echo "Running console error detection tests..."
	cd frontend && npm run test:e2e -- console-errors.spec.js

dev:
	@echo "Starting local development server..."
	cd frontend && npm run dev

install-playwright:
	uv run playwright install chromium firefox webkit

outputs:
	@echo "=== CDK Stack Outputs ==="
	@echo ""
	@echo "Current branch: $(BRANCH)"
	@echo "Stack prefix: $(STACK_PREFIX)"
	@echo ""
	@echo "Site Stack (us-east-1):"
	@aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-site --region us-east-1 --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output text 2>/dev/null | column -t || echo "Stack not found"
	@echo ""
	@echo "Auth Stack (ap-southeast-2):"
	@aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-auth --region ap-southeast-2 --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output text 2>/dev/null | column -t || echo "Stack not found"
	@echo ""
	@echo "=== Quick Access URLs ==="
	@echo -n "CloudFront URL: https://"
	@aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-site --region us-east-1 --query 'Stacks[0].Outputs[?OutputKey==`DistributionDomainName`].OutputValue' --output text 2>/dev/null || echo "Not deployed"

diagram: synth
	@echo "Generating architecture diagram..."
	@mkdir -p docs/images
	npx cdk-dia --target-path docs/images/architecture.png
	@echo "Architecture diagram generated at docs/images/architecture.png"

# Generate both aws-exports.js and Lambda@Edge code from stack outputs
generate-configs:
	@uv run scripts/generate_configs.py

# Standalone targets for manual use
generate-aws-exports:
	@echo "Generating aws-exports.js from stack outputs..."
	uv run scripts/generate_aws_exports.py

generate-lambda-code:
	@echo "Generating Lambda@Edge code from template..."
	uv run scripts/generate_lambda_code.py

# Run deployment triage and status analysis
triage:
	@echo "Running deployment triage..."
	uv run scripts/triage_deployment.py

check-lambda-propagation:
	@echo "Checking Lambda@Edge propagation status..."
	uv run scripts/check_lambda_propagation.py

# List all feature branch stacks
list-feature-stacks:
	@echo "=== Feature Branch Stacks ==="
	@echo "REGION: ap-southeast-2"
	@aws cloudformation list-stacks --region ap-southeast-2 --query 'StackSummaries[?contains(StackName, `sflt-`) && StackStatus != `DELETE_COMPLETE`].[StackName,StackStatus,CreationTime]' --output table
	@echo "REGION: us-east-1"
	@aws cloudformation list-stacks --region us-east-1 --query 'StackSummaries[?contains(StackName, `sflt-`) && StackStatus != `DELETE_COMPLETE`].[StackName,StackStatus,CreationTime]' --output table

# Enhanced cleanup targets
cleanup-feature-branches:
	@echo "Finding old feature branch stacks..."
	@uv run scripts/cleanup_feature_branches.py

cleanup-lambda-edge:
	@echo "Cleaning up Lambda@Edge blocked stacks..."
	@uv run scripts/cleanup_feature_branches.py --lambda-edge-retry

cleanup-all:
	@echo "Running comprehensive cleanup (old stacks + Lambda@Edge retries)..."
	@uv run scripts/cleanup_feature_branches.py --include-lambda-edge-retry

list-blocked-stacks:
	@echo "=== Lambda@Edge Blocked Stacks ==="
	@uv run scripts/cleanup_feature_branches.py --list-blocked

destroy-retry:
	@echo "Retrying destruction with enhanced Lambda@Edge handling..."
	@uv run scripts/destroy_orchestrator.py

fix:
	uv run ruff format . --respect-gitignore
	uv run ruff check --respect-gitignore --fix-only .
	uv run ruff check --respect-gitignore --statistics .