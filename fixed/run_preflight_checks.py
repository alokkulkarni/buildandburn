def run_preflight_checks(manifest, env_id, terraform_project_dir):
    """
    Run pre-flight checks to ensure everything is properly configured.
    
    This function validates AWS credentials, region setting, and Terraform configuration
    before attempting to provision infrastructure.
    
    Args:
        manifest (dict): The parsed manifest containing configuration
        env_id (str): Unique environment ID for this deployment
        terraform_project_dir (str): Path to Terraform project directory
        
    Returns:
        bool: True if all checks pass, False otherwise
    """
    print_info("=" * 80)
    print_info("RUNNING PRE-FLIGHT CHECKS")
    print_info("=" * 80)
    
    # Check AWS CLI configuration
    print_info("Checking AWS CLI configuration...")
    try:
        aws_version_result = run_command(["aws", "--version"], capture_output=True)
        print_info(f"AWS CLI: {aws_version_result.stdout.strip()}")
        
        # Check AWS identity
        aws_identity = run_command(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], 
                                  capture_output=True)
        if aws_identity.returncode == 0:
            print_info("AWS Identity check passed")
        else:
            print_error("AWS CLI is not properly configured. Please run 'aws configure'")
            return False
        
        # Set AWS region if provided in manifest
        region = manifest.get('region', 'us-west-2')
        print_info(f"Using AWS region: {region}")
        
        # Set region in AWS config if needed
        os.environ["AWS_REGION"] = region
        os.environ["AWS_DEFAULT_REGION"] = region
        
    except Exception as e:
        print_error(f"Failed to check AWS configuration: {str(e)}")
        return False
    
    # Check Terraform configuration
    print_info("Checking Terraform configuration...")
    try:
        tf_version_result = run_command(["terraform", "--version"], capture_output=True)
        print_info(f"Terraform: {tf_version_result.stdout.split('\\n')[0]}")
        
        # Validate Terraform configuration
        if not os.path.exists(terraform_project_dir):
            print_error(f"Terraform directory not found: {terraform_project_dir}")
            return False
        
    except Exception as e:
        print_error(f"Failed to check Terraform configuration: {str(e)}")
        return False
    
    # Check kubectl
    print_info("Checking kubectl...")
    try:
        kubectl_version_result = run_command(["kubectl", "version", "--client", "--output=yaml"], 
                                           capture_output=True, allow_fail=True)
        if kubectl_version_result.returncode == 0:
            print_info("kubectl client detected")
        else:
            print_warning("kubectl not found or not properly configured")
            print_warning("You may need to install kubectl if you plan to interact with the Kubernetes cluster")
    except Exception as e:
        print_warning(f"Could not check kubectl: {str(e)}")
    
    # Check Helm
    print_info("Checking Helm...")
    try:
        helm_version_result = run_command(["helm", "version", "--short"], 
                                        capture_output=True, allow_fail=True)
        if helm_version_result.returncode == 0:
            print_info(f"Helm: {helm_version_result.stdout.strip()}")
        else:
            print_warning("Helm not found or not properly configured")
            print_warning("You may need to install Helm if you plan to deploy applications via Helm charts")
    except Exception as e:
        print_warning(f"Could not check Helm: {str(e)}")
    
    print_info("All pre-flight checks passed!")
    
    # Verify AWS credentials
    try:
        account_id_result = run_command(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            capture_output=True
        )
        account_id = account_id_result.stdout.strip()
        print_info(f"Using AWS Account: {account_id}")
        
        # Set region
        print_info(f"Setting AWS region to: {region}")
        region_result = run_command(
            ["aws", "configure", "get", "region"],
            capture_output=True, allow_fail=True
        )
        current_region = region_result.stdout.strip() if region_result.returncode == 0 else None
        
        if current_region != region:
            print_warning(f"Current AWS CLI region ({current_region}) doesn't match manifest region ({region})")
            print_info(f"Using manifest region: {region}")
        
    except Exception as e:
        print_error(f"Failed to verify AWS credentials: {str(e)}")
        return False
    
    return True 