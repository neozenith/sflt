#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate Lambda@Edge function code from template with CDK values."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict


# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_info(message: str):
    print(f"{Colors.BLUE}ℹ {message}{Colors.ENDC}")


def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")


def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.ENDC}")


def print_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")


def get_stack_outputs(stack_name: str, region: str) -> Dict[str, str]:
    """Get CloudFormation stack outputs."""
    try:
        cmd = [
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", stack_name,
            "--region", region,
            "--query", "Stacks[0].Outputs",
            "--output", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if not result.stdout:
            return {}
            
        outputs_list = json.loads(result.stdout)
        outputs = {}
        
        if outputs_list:
            for output in outputs_list:
                outputs[output['OutputKey']] = output['OutputValue']
                
        return outputs
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to get stack outputs for {stack_name}: {e}")
        return {}
    except json.JSONDecodeError as e:
        print_error(f"Failed to parse stack outputs: {e}")
        return {}


def generate_lambda_code(template_path: Path, output_path: Path, template_vars: Dict[str, str]) -> bool:
    """Generate Lambda function code from template."""
    try:
        # Read template
        if not template_path.exists():
            print_error(f"Template file not found: {template_path}")
            return False
            
        template_content = template_path.read_text()
        
        # Replace template variables
        generated_content = template_content
        for key, value in template_vars.items():
            placeholder = f"{{{{{key}}}}}"
            generated_content = generated_content.replace(placeholder, value)
            
        # Check if all placeholders were replaced
        if "{{" in generated_content and "}}" in generated_content:
            print_warning("Some template variables may not have been replaced")
            
        # Write output
        output_path.write_text(generated_content)
        print_success(f"Generated Lambda code: {output_path}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to generate Lambda code: {e}")
        return False


def main():
    """Main function to generate Lambda@Edge code from template."""
    print_info("Generating Lambda@Edge code from template...")
    
    # Get script directory and project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Paths
    template_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py.template"
    output_path = project_root / "cdk" / "lambda-edge" / "auth_handler.py"
    
    # Get Auth Stack outputs
    print_info("Fetching Auth Stack outputs...")
    auth_outputs = get_stack_outputs('SfltAuthStack', 'ap-southeast-2')
    
    if not auth_outputs:
        print_error("No Auth Stack outputs found. Is the stack deployed?")
        return 1
    
    # Extract required values
    required_values = {
        'COGNITO_DOMAIN': auth_outputs.get('UserPoolDomainName', '') + '.auth.ap-southeast-2.amazoncognito.com',
        'COGNITO_CLIENT_ID': auth_outputs.get('UserPoolClientId', ''),
        'COGNITO_REGION': 'ap-southeast-2',
        'USER_POOL_ID': auth_outputs.get('UserPoolId', ''),
    }
    
    # Check for missing values
    missing_values = [key for key, value in required_values.items() if not value]
    if missing_values:
        print_error(f"Missing required values: {missing_values}")
        return 1
    
    # Log what we're using
    print_info("Template variables:")
    for key, value in required_values.items():
        print(f"  {key}: {value}")
    
    # Generate the code
    if generate_lambda_code(template_path, output_path, required_values):
        print_success("Lambda@Edge code generated successfully!")
        return 0
    else:
        print_error("Failed to generate Lambda@Edge code")
        return 1


if __name__ == "__main__":
    sys.exit(main())