import subprocess
import re

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