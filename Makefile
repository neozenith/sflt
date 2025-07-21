.PHONY: help install install-frontend build build-frontend deploy deploy-converge post-deploy synth diff destroy clean test test-e2e test-e2e-local test-console-errors dev lint format bootstrap outputs diagram generate-aws-exports generate-lambda-code triage

export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

help:
	@echo "Available commands:"
	@echo "  make install          - Install all dependencies (Python and frontend)"
	@echo "  make build            - Build everything (frontend and CDK)"
	@echo "  make deploy           - Deploy the stack to AWS"
	@echo "  make deploy-converge  - Deploy then auto-converge configuration if needed"
	@echo "  make destroy          - Destroy the stack in AWS"
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
	@echo "  make generate-aws-exports - Generate aws-exports.js from stack outputs"
	@echo "  make generate-lambda-code - Generate Lambda@Edge code from template"
	@echo "  make triage              - Run deployment triage and status analysis"
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

build: build-frontend generate-lambda-code synth

build-frontend:
	cd frontend && npm run build

synth:
	uv run cdk synth --all

diff:
	uv run cdk diff

deploy: build
	uv run cdk deploy --all --require-approval never

# Deploy with automatic convergence - handles circular dependency
deploy-converge:
	@echo "Starting deployment with auto-convergence..."
	@$(MAKE) deploy
	@echo "Checking for configuration drift..."
	@if uv run scripts/generate_aws_exports.py; then \
		echo "✓ Configuration is up to date"; \
	elif [ $$? -eq 2 ]; then \
		echo "⚠ Configuration drift detected - rebuilding and redeploying..."; \
		$(MAKE) build-frontend; \
		$(MAKE) generate-lambda-code; \
		uv run cdk deploy SfltStaticSiteStack --require-approval never; \
		echo "✓ Convergence complete"; \
	else \
		echo "✗ Failed to generate configuration"; \
		exit 1; \
	fi

# Post-deployment check only (for manual use)
post-deploy:
	@echo "Checking for configuration drift..."
	@uv run scripts/generate_aws_exports.py || exit $$?

destroy:
	uv run cdk destroy --force

clean:
	rm -rf cdk.out
	rm -rf frontend/dist
	rm -rf frontend/build
	rm -rf tmp/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.orig" -delete
	find . -type f -name "*.bak" -delete
	find . -type f -name "*.tmp" -delete

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
	@echo
	@echo "Static Site Stack (us-east-1):"
	@aws cloudformation describe-stacks --stack-name SfltStaticSiteStack --region us-east-1 --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output text 2>/dev/null | column -t || echo "Stack not found"
	@echo
	@echo "Auth Stack (ap-southeast-2):"
	@aws cloudformation describe-stacks --stack-name SfltAuthStack --region ap-southeast-2 --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output text 2>/dev/null | column -t || echo "Stack not found"
	@echo
	@echo "=== Quick Access URLs ==="
	@echo -n "CloudFront URL: https://"
	@aws cloudformation describe-stacks --stack-name SfltStaticSiteStack --region us-east-1 --query 'Stacks[0].Outputs[?OutputKey==`DistributionDomainName`].OutputValue' --output text 2>/dev/null || echo "Not deployed"
	@echo
	@echo "JSON outputs saved to tmp/triage-cache/combined_outputs.json"

diagram: synth
	@echo "Generating architecture diagram..."
	@mkdir -p docs/images
	npx cdk-dia --target-path docs/images/architecture.png
	@echo "Architecture diagram generated at docs/images/architecture.png"

# Generate aws-exports.js from CDK stack outputs
generate-aws-exports:
	@echo "Generating aws-exports.js from stack outputs..."
	uv run scripts/generate_aws_exports.py

# Generate Lambda@Edge code from template
generate-lambda-code:
	@echo "Generating Lambda@Edge code from template..."
	uv run scripts/generate_lambda_code.py

# Run deployment triage and status analysis
triage:
	@echo "Running deployment triage..."
	uv run scripts/triage_deployment.py