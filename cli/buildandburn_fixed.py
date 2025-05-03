import subprocess
import re
import json

# Constants
TERRAFORM_MIN_VERSION = "1.0.0"
KUBECTL_MIN_VERSION = "1.20.0"
AWS_CLI_MIN_VERSION = "2.0.0"

def print_color(text, color_code):
    """
    Print text with specified color code.
    
    Args:
        text (str): The text to print
        color_code (str): ANSI color code to use
    """
    print(f"\033[{color_code}m{text}\033[0m")

def print_success(text):
    """Print success message in green."""
    print_color(f"✅ {text}", "92")

def print_info(text):
    """Print information message in blue."""
    print_color(f"ℹ️ {text}", "94")

def print_warning(text):
    """Print warning message in yellow."""
    print_color(f"⚠️ {text}", "93")

def print_error(text):
    """Print error message in red."""
    print_color(f"❌ {text}", "91")

def is_terraform_installed():
    """
    Check if Terraform is installed and meets the minimum version requirement.
    
    Returns:
        tuple: (bool, str) - Whether Terraform is installed and meets requirements,
               and the installed version string
    """
    try:
        result = subprocess.run(["terraform", "--version"], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False, None
        
        # Extract version number
        match = re.search(r'Terraform v(\d+\.\d+\.\d+)', result.stdout)
        if not match:
            return False, None
        
        version = match.group(1)
        # Check if version meets minimum requirement
        version_parts = list(map(int, version.split('.')))
        min_version_parts = list(map(int, TERRAFORM_MIN_VERSION.split('.')))
        
        # Compare version components
        for i in range(len(min_version_parts)):
            if i >= len(version_parts):
                return False, version
            if version_parts[i] < min_version_parts[i]:
                return False, version
            if version_parts[i] > min_version_parts[i]:
                break
        
        return True, version
    except Exception as e:
        print_error(f"Error checking Terraform installation: {str(e)}")
        return False, None

def is_kubectl_installed():
    """
    Check if kubectl is installed and meets the minimum version requirement.
    
    Returns:
        tuple: (bool, str) - Whether kubectl is installed and meets requirements,
               and the installed version string
    """
    try:
        result = subprocess.run(["kubectl", "version", "--client", "--output=json"], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            # Try the older version format
            result = subprocess.run(["kubectl", "version", "--client"], 
                                  capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return False, None
            
            # Extract version from text output
            match = re.search(r'Client Version: v?(\d+\.\d+\.\d+)', result.stdout)
            if not match:
                return False, None
            version = match.group(1)
        else:
            # Parse JSON output
            try:
                version_info = json.loads(result.stdout)
                if 'clientVersion' in version_info:
                    version = version_info['clientVersion']['gitVersion'].lstrip('v')
                else:
                    version = version_info['kustomizeVersion'].lstrip('v')
            except json.JSONDecodeError:
                # Fallback to regex if JSON parsing fails
                match = re.search(r'Client Version: v?(\d+\.\d+\.\d+)', result.stdout)
                if not match:
                    return False, None
                version = match.group(1)
        
        # Check version meets minimum requirement (simplified for example)
        version_parts = list(map(int, version.split('.')))
        min_version_parts = list(map(int, KUBECTL_MIN_VERSION.split('.')))
        
        for i in range(len(min_version_parts)):
            if i >= len(version_parts):
                return False, version
            if version_parts[i] < min_version_parts[i]:
                return False, version
            if version_parts[i] > min_version_parts[i]:
                break
        
        return True, version
    except Exception as e:
        print_error(f"Error checking kubectl installation: {str(e)}")
        return False, None 

def is_aws_cli_installed():
    """
    Check if AWS CLI is installed and meets the minimum version requirement.
    
    Returns:
        tuple: (bool, str) - Whether AWS CLI is installed and meets requirements,
               and the installed version string
    """
    try:
        result = subprocess.run(["aws", "--version"], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False, None
        
        # Extract version number
        match = re.search(r'aws-cli/(\d+\.\d+\.\d+)', result.stdout)
        if not match:
            return False, None
        
        version = match.group(1)
        
        # Check if version meets minimum requirement
        version_parts = list(map(int, version.split('.')))
        min_version_parts = list(map(int, AWS_CLI_MIN_VERSION.split('.')))
        
        for i in range(len(min_version_parts)):
            if i >= len(version_parts):
                return False, version
            if version_parts[i] < min_version_parts[i]:
                return False, version
            if version_parts[i] > min_version_parts[i]:
                break
        
        return True, version
    except Exception as e:
        print_error(f"Error checking AWS CLI installation: {str(e)}")
        return False, None

def check_prerequisites():
    """
    Check if all required prerequisites are installed.
    
    This function verifies that Terraform, kubectl, and AWS CLI are installed
    and meet the minimum version requirements.
    
    Returns:
        bool: True if all prerequisites are installed and meet requirements
    """
    print_info("=" * 79)
    print_info("CHECKING PREREQUISITES")
    print_info("=" * 79)
    
    # Check Terraform
    tf_installed, tf_version = is_terraform_installed()
    if tf_installed:
        print_info(f"Terraform version {tf_version} found.")
    else:
        print_error(f"Terraform version {TERRAFORM_MIN_VERSION} or higher is required.")
        print_error("Please install Terraform: https://learn.hashicorp.com/tutorials/terraform/install-cli")
        return False
    
    # Check AWS CLI
    aws_installed, aws_version = is_aws_cli_installed()
    if aws_installed:
        print_info(f"AWS CLI version {aws_version} found.")
    else:
        print_error(f"AWS CLI version {AWS_CLI_MIN_VERSION} or higher is required.")
        print_error("Please install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        return False
    
    # Check kubectl
    kubectl_installed, kubectl_version = is_kubectl_installed()
    if kubectl_installed:
        print_info(f"kubectl version {kubectl_version} found.")
    else:
        print_error(f"kubectl version {KUBECTL_MIN_VERSION} or higher is required.")
        print_error("Please install kubectl: https://kubernetes.io/docs/tasks/tools/")
        return False
    
    print_info("All prerequisites are installed.")
    return True 