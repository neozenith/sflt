#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
#   "rich",
#   "jinja2",
# ]
# ///
"""Generate Lambda@Edge function code from template with CDK values."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared utilities
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from orchestration_utils import configure_logging, console, get_stack_outputs
from rich.syntax import Syntax

from cdk.config import get_deployment_config

logger = configure_logging()


def generate_lambda_code_with_jinja2(
    template_path: Path, output_path: Path, template_vars: dict[str, str], verbose: bool = True
) -> bool:
    """Generate Lambda function code from template using Jinja2.

    Args:
        template_path: Path to Jinja2 template file
        output_path: Path where generated code will be written
        template_vars: Dictionary of template variables
        verbose: Whether to print progress messages

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check template exists
        if not template_path.exists():
            if verbose:
                console.print(f"[red]✗[/red] Template file not found: [yellow]{template_path}[/yellow]")
            return False

        # Set up Jinja2 environment with StrictUndefined for fail-fast on missing variables
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

        # Load template
        template = env.get_template(template_path.name)

        # Render template with variables
        generated_content = template.render(**template_vars)

        # Write output
        output_path.write_text(generated_content)

        if verbose:
            console.print(f"[green]✓[/green] Generated Lambda code: [cyan]{output_path}[/cyan]")

            # Show a preview with syntax highlighting
            console.print("\n[bold]Generated code preview:[/bold]")
            syntax = Syntax(
                generated_content[:500] + "..." if len(generated_content) > 500 else generated_content,
                "python",
                theme="monokai",
                line_numbers=False,
            )
            console.print(syntax)

        return True

    except Exception as e:
        if verbose:
            console.print(f"[red]✗[/red] Failed to generate Lambda code: [red]{e}[/red]")
        return False


def generate_lambda_code_from_template(verbose: bool = True) -> bool:
    """Generate Lambda@Edge code from template using current stack outputs.

    Args:
        verbose: Whether to print detailed output

    Returns:
        True if successful, False otherwise
    """
    # Get deployment configuration
    config = get_deployment_config()

    # Get script directory and project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Paths
    template_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py.template"
    output_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py"

    # Get Auth Stack outputs
    auth_stack_data = get_stack_outputs(config.auth_stack_name, config.auth_region, use_cache=True)

    if not auth_stack_data:
        if verbose:
            console.print(
                f"[red]✗[/red] No Auth Stack outputs found for {config.auth_stack_name}. Is the stack deployed?"
            )
        return False

    auth_outputs = auth_stack_data.get("Outputs", {})

    # Extract required values
    required_values = {
        "COGNITO_DOMAIN": auth_outputs.get("UserPoolDomainName", "") + f".auth.{config.auth_region}.amazoncognito.com",
        "COGNITO_CLIENT_ID": auth_outputs.get("UserPoolClientId", ""),
        "COGNITO_REGION": config.auth_region,
        "USER_POOL_ID": auth_outputs.get("UserPoolId", ""),
    }

    # Check for missing values
    missing_values = [
        key for key, value in required_values.items() if not value or value.endswith(".auth..amazoncognito.com")
    ]
    if missing_values:
        if verbose:
            console.print(f"[red]✗[/red] Missing required values: [yellow]{missing_values}[/yellow]")
        return False

    # Log what we're using
    if verbose:
        console.print("\n[bold]Template variables:[/bold]")
        for key, value in required_values.items():
            console.print(f"  [cyan]{key}:[/cyan] [yellow]{value}[/yellow]")

    # Generate the code with Jinja2
    return generate_lambda_code_with_jinja2(template_path, output_path, required_values, verbose=verbose)


def main():
    """Main function to generate Lambda@Edge code from template."""
    console.rule("[bold magenta]Lambda@Edge Code Generator[/bold magenta]")

    # Get deployment configuration
    config = get_deployment_config()

    console.print(f"\n[dim]Environment: [cyan]{config.environment}[/cyan][/dim]")
    console.print(f"[dim]Branch: [cyan]{config.branch}[/cyan][/dim]")
    console.print(f"[dim]Auth Stack: [yellow]{config.auth_stack_name}[/yellow][/dim]")

    # Generate the code
    if generate_lambda_code_from_template(verbose=True):
        console.print("\n[green]✓[/green] [bold]Lambda@Edge code generated successfully![/bold]")
        return 0
    else:
        console.print("[red]✗[/red] Failed to generate Lambda@Edge code")
        return 1


if __name__ == "__main__":
    sys.exit(main())
