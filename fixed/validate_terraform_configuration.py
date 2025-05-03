def validate_terraform_configuration(terraform_project_dir):
    """
    Validate Terraform configuration files.
    
    This function runs 'terraform fmt' and 'terraform validate' to check that
    the Terraform configuration is properly formatted and syntactically correct.
    
    Args:
        terraform_project_dir (str): Path to Terraform project directory
        
    Returns:
        tuple: (bool, str) - Success status and error message if any
    """
    print_info("=" * 80)
    print_info("VALIDATING TERRAFORM CONFIGURATION")
    print_info("=" * 80)
    
    try:
        # First, check if Terraform is installed
        tf_version_result = run_command(["terraform", "--version"], capture_output=True)
        print_info(f"Terraform version {tf_version_result.stdout.split()[1]} found.")
        
        # Check Terraform files
        tf_files = glob.glob(os.path.join(terraform_project_dir, "**/*.tf"), recursive=True)
        print_info(f"Found {len(tf_files)} Terraform files.")
        
        # Check formatting
        print_info("Executing command: ['terraform', 'fmt', '-check', '-recursive']")
        print_info(f"Working directory: {terraform_project_dir}")
        format_result = subprocess.run(
            ["terraform", "fmt", "-check", "-recursive"],
            cwd=terraform_project_dir,
            capture_output=True,
            text=True
        )
        
        if format_result.returncode != 0:
            print_warning("Terraform files are not properly formatted. Running terraform fmt...")
            fmt_fix_result = subprocess.run(
                ["terraform", "fmt", "-recursive"],
                cwd=terraform_project_dir,
                capture_output=True,
                text=True
            )
            if fmt_fix_result.returncode != 0:
                print_error("Failed to format Terraform files")
                print_error(fmt_fix_result.stderr)
                return False, "Failed to format Terraform files"
            else:
                print_success("Terraform files have been formatted.")
        else:
            print_info("Terraform files are properly formatted.")
    
        # Run standard validation
        print_info("Running standard validation...")
        validate_result = subprocess.run(
            ["terraform", "validate"],
            cwd=terraform_project_dir,
            capture_output=True,
            text=True
        )
        
        if validate_result.returncode != 0:
            print_error("Terraform validation failed:")
            print_error(validate_result.stderr)
            
            # Generate debug log
            debug_log_path = os.path.join(terraform_project_dir, "terraform_validate_debug.log")
            with open(debug_log_path, "w") as log_file:
                log_file.write("TERRAFORM VALIDATION ERROR\n")
                log_file.write("=" * 80 + "\n")
                log_file.write(f"Command: terraform validate\n")
                log_file.write(f"Working directory: {terraform_project_dir}\n")
                log_file.write("-" * 80 + "\n")
                log_file.write("STDOUT:\n")
                log_file.write(validate_result.stdout)
                log_file.write("\n" + "-" * 80 + "\n")
                log_file.write("STDERR:\n")
                log_file.write(validate_result.stderr)
            
            print_info(f"Debug log written to: {debug_log_path}")
            
            # Try to fix common issues
            fixed = False
            if "provider configuration is required" in validate_result.stderr:
                print_info("Attempting to fix missing provider configuration...")
                if add_provider_config(terraform_project_dir):
                    fixed = True
            
            if fixed:
                print_info("Trying validation again after fixes...")
                revalidate_result = subprocess.run(
                    ["terraform", "validate"],
                    cwd=terraform_project_dir,
                    capture_output=True,
                    text=True
                )
                
                if revalidate_result.returncode != 0:
                    print_error("Terraform validation still failed after fixes:")
                    print_error(revalidate_result.stderr)
                    return False, "Terraform validation failed even after fixes"
                else:
                    print_success("Terraform validation succeeded after fixes!")
            else:
                return False, "Terraform validation failed"
        else:
            print_success(validate_result.stdout.strip())
        
        print_success("Terraform validation succeeded!")
        return True, ""
    
    except Exception as e:
        print_error(f"Error validating Terraform configuration: {str(e)}")
        traceback.print_exc()
        return False, str(e) 