#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "rich",
# ]
# ///
"""Test the configuration convergence functionality."""

import logging
import subprocess
import sys
from pathlib import Path

# Configure Rich logging
from rich.console import Console
from rich.logging import RichHandler

console = Console()
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False, show_time=False)]
)
logger = logging.getLogger(__name__)


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_convergence():
    """Test the convergence detection functionality."""
    console.rule("[bold magenta]Configuration Convergence Test[/bold magenta]")

    # Path to aws-exports.js
    aws_exports_path = Path(__file__).parent.parent / "frontend" / "src" / "aws-exports.js"

    # Backup current file
    if aws_exports_path.exists():
        original_content = aws_exports_path.read_text()
        console.print("[dim]Backed up original aws-exports.js[/dim]")
    else:
        original_content = None
        console.print("[yellow]No existing aws-exports.js found[/yellow]")

    try:
        # Test 1: Corrupt the CloudFront domain
        console.rule("[bold blue]Test 1: Simulating CloudFront domain drift[/bold blue]")
        if original_content:
            corrupted_content = original_content.replace("d3nteozhns257o.cloudfront.net", "old-domain.cloudfront.net")
            aws_exports_path.write_text(corrupted_content)

        # Run convergence check
        exit_code, stdout, stderr = run_command(["uv", "run", "scripts/generate_aws_exports.py"])

        if exit_code == 2:
            console.print("[green]✓[/green] Correctly detected configuration drift ([cyan]exit code 2[/cyan])")
        else:
            console.print(f"[red]✗[/red] Failed to detect drift ([red]exit code {exit_code}[/red])")
            return False

        # Test 2: Generate correct config
        console.rule("[bold blue]Test 2: Generating correct configuration[/bold blue]")
        new_content = aws_exports_path.read_text()

        if "d3nteozhns257o.cloudfront.net" in new_content:
            console.print("[green]✓[/green] Configuration correctly regenerated")
        else:
            console.print("[red]✗[/red] Configuration not regenerated correctly")
            return False

        # Test 3: Run again - should detect no drift
        console.rule("[bold blue]Test 3: Verifying no drift after correction[/bold blue]")
        exit_code, stdout, stderr = run_command(["uv", "run", "scripts/generate_aws_exports.py"])

        if exit_code == 0:
            console.print("[green]✓[/green] Correctly detected no drift ([cyan]exit code 0[/cyan])")
        else:
            console.print(f"[red]✗[/red] Incorrectly detected drift ([red]exit code {exit_code}[/red])")
            return False

        console.rule("[bold green]Test Results[/bold green]")
        console.print("[green]✅[/green] [bold]All tests passed![/bold]")
        return True

    finally:
        # Restore original file
        if original_content:
            aws_exports_path.write_text(original_content)
            console.print("\n[dim]Restored original aws-exports.js[/dim]")


if __name__ == "__main__":
    success = test_convergence()
    sys.exit(0 if success else 1)
