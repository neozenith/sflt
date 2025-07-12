#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Test the configuration convergence functionality."""

import subprocess
import sys
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_convergence():
    """Test the convergence detection functionality."""
    print(f"{Colors.BLUE}Testing configuration convergence...{Colors.ENDC}")
    
    # Path to aws-exports.js
    aws_exports_path = Path(__file__).parent.parent / "frontend" / "src" / "aws-exports.js"
    
    # Backup current file
    if aws_exports_path.exists():
        original_content = aws_exports_path.read_text()
        print(f"{Colors.BLUE}Backed up original aws-exports.js{Colors.ENDC}")
    else:
        original_content = None
        print(f"{Colors.YELLOW}No existing aws-exports.js found{Colors.ENDC}")
    
    try:
        # Test 1: Corrupt the CloudFront domain
        print(f"\n{Colors.BOLD}Test 1: Simulating CloudFront domain drift{Colors.ENDC}")
        if original_content:
            corrupted_content = original_content.replace("d3nteozhns257o.cloudfront.net", "old-domain.cloudfront.net")
            aws_exports_path.write_text(corrupted_content)
        
        # Run convergence check
        exit_code, stdout, stderr = run_command(["uv", "run", "scripts/generate_aws_exports.py"])
        
        if exit_code == 2:
            print(f"{Colors.GREEN}✓ Correctly detected configuration drift (exit code 2){Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ Failed to detect drift (exit code {exit_code}){Colors.ENDC}")
            return False
            
        # Test 2: Generate correct config
        print(f"\n{Colors.BOLD}Test 2: Generating correct configuration{Colors.ENDC}")
        new_content = aws_exports_path.read_text()
        
        if "d3nteozhns257o.cloudfront.net" in new_content:
            print(f"{Colors.GREEN}✓ Configuration correctly regenerated{Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ Configuration not regenerated correctly{Colors.ENDC}")
            return False
            
        # Test 3: Run again - should detect no drift
        print(f"\n{Colors.BOLD}Test 3: Verifying no drift after correction{Colors.ENDC}")
        exit_code, stdout, stderr = run_command(["uv", "run", "scripts/generate_aws_exports.py"])
        
        if exit_code == 0:
            print(f"{Colors.GREEN}✓ Correctly detected no drift (exit code 0){Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ Incorrectly detected drift (exit code {exit_code}){Colors.ENDC}")
            return False
            
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.ENDC}")
        return True
        
    finally:
        # Restore original file
        if original_content:
            aws_exports_path.write_text(original_content)
            print(f"\n{Colors.BLUE}Restored original aws-exports.js{Colors.ENDC}")


if __name__ == "__main__":
    success = test_convergence()
    sys.exit(0 if success else 1)