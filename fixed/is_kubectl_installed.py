import subprocess
import re
import json

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