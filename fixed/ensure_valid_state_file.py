def ensure_valid_state_file(state_file_path, terraform_dir=None):
    """
    Ensure that a Terraform state file is valid.
    
    This function checks if a state file exists and has proper structure.
    If it doesn't, it attempts to fix the file.
    
    Args:
        state_file_path (str): Path to the state file
        terraform_dir (str, optional): Path to Terraform directory
        
    Returns:
        bool: True if state file was fixed or is already valid, False otherwise
    """
    try:
        # Check if state file exists
        if not os.path.exists(state_file_path):
            print_warning(f"State file not found: {state_file_path}")
            return False
        
        # Check if state file is valid JSON
        with open(state_file_path, 'r') as f:
            try:
                state_data = json.load(f)
            except json.JSONDecodeError:
                print_warning(f"State file is not valid JSON: {state_file_path}")
                return create_valid_state_file(state_file_path, terraform_dir)
        
        # Check if state file has required fields
        required_fields = ['version', 'terraform_version', 'serial', 'lineage', 'resources']
        for field in required_fields:
            if field not in state_data:
                print_warning(f"State file is missing required field '{field}': {state_file_path}")
                return create_valid_state_file(state_file_path, terraform_dir)
        
        return True
    except Exception as e:
        print_error(f"Failed to check state file: {str(e)}")
        return False 