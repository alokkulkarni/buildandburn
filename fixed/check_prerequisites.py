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