#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "rich",
# ]
# ///
"""Generate Lambda@Edge function code from template with CDK values."""

import json
import logging
import subprocess
import sys
from pathlib import Path

# Configure Rich logging
from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)


def get_stack_outputs(stack_name: str, region: str) -> dict[str, str]:
    """Get CloudFormation stack outputs."""
    try:
        cmd = [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack_name,
            "--region",
            region,
            "--query",
            "Stacks[0].Outputs",
            "--output",
            "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if not result.stdout:
            return {}

        outputs_list = json.loads(result.stdout)
        outputs = {}

        if outputs_list:
            for output in outputs_list:
                outputs[output["OutputKey"]] = output["OutputValue"]

        return outputs

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get stack outputs for {stack_name}: {e}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse stack outputs: {e}")
        return {}


def generate_lambda_code(template_path: Path, output_path: Path, template_vars: dict[str, str]) -> bool:
    """Generate Lambda function code from template."""
    try:
        # Read template
        if not template_path.exists():
            console.print(f"[red]✗[/red] Template file not found: [yellow]{template_path}[/yellow]")
            return False

        template_content = template_path.read_text()

        # Replace template variables
        generated_content = template_content
        for key, value in template_vars.items():
            placeholder = f"{{{{{key}}}}}"
            generated_content = generated_content.replace(placeholder, value)

        # Check if all placeholders were replaced
        if "{{" in generated_content and "}}" in generated_content:
            console.print("[yellow]Some template variables may not have been replaced[/yellow]")

        # Write output
        output_path.write_text(generated_content)
        console.print(f"[green]✓[/green] Generated Lambda code: [cyan]{output_path}[/cyan]")

        # Show a preview of the generated code with syntax highlighting
        console.print("\n[bold]Generated code preview:[/bold]")
        syntax = Syntax(generated_content[:500] + "..." if len(generated_content) > 500 else generated_content,
                       "python", theme="monokai", line_numbers=False)
        console.print(syntax)

        return True

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to generate Lambda code: [red]{e}[/red]")
        return False


def main():
    """Main function to generate Lambda@Edge code from template."""
    console.rule("[bold magenta]Lambda@Edge Code Generator[/bold magenta]")

    # Get script directory and project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Paths
    template_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py.template"
    output_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py"

    # Get Auth Stack outputs
    console.print("[dim]Fetching Auth Stack outputs...[/dim]")
    auth_outputs = get_stack_outputs("SfltAuthStack", "ap-southeast-2")

    if not auth_outputs:
        console.print("[red]✗[/red] No Auth Stack outputs found. Is the stack deployed?")
        return 1

    # Extract required values
    required_values = {
        "COGNITO_DOMAIN": auth_outputs.get("UserPoolDomainName", "") + ".auth.ap-southeast-2.amazoncognito.com",
        "COGNITO_CLIENT_ID": auth_outputs.get("UserPoolClientId", ""),
        "COGNITO_REGION": "ap-southeast-2",
        "USER_POOL_ID": auth_outputs.get("UserPoolId", ""),
    }

    # Check for missing values
    missing_values = [key for key, value in required_values.items() if not value]
    if missing_values:
        console.print(f"[red]✗[/red] Missing required values: [yellow]{missing_values}[/yellow]")
        return 1

    # Log what we're using
    console.print("\n[bold]Template variables:[/bold]")
    for key, value in required_values.items():
        console.print(f"  [cyan]{key}:[/cyan] [yellow]{value}[/yellow]")

    # Generate the code
    if generate_lambda_code(template_path, output_path, required_values):
        console.print("\n[green]✓[/green] [bold]Lambda@Edge code generated successfully![/bold]")
        return 0
    else:
        console.print("[red]✗[/red] Failed to generate Lambda@Edge code")
        return 1


if __name__ == "__main__":
    sys.exit(main())
