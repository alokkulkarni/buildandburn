#!/usr/bin/env python3
"""
Dry validation script for buildandburn.py
This script validates the buildandburn.py with a sample manifest file
without actually creating any infrastructure.
"""

import os
import sys
import json
import yaml
import argparse
import shutil
from pathlib import Path

# Add the current directory to the path so we can import from cli module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cli.buildandburn import (
    print_info, print_error, print_success, print_warning,
    load_manifest, generate_env_id, prepare_terraform_vars,
    run_preflight_checks, validate_terraform_modules_against_manifest,
    apply_terraform_module_fixes, generate_resource_summary
)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Dry validate the buildandburn.py script")
    parser.add_argument("-m", "--manifest", required=True, help="Path to the manifest file")
    parser.add_argument("-i", "--env-id", help="Environment ID (generated if not provided)")
    return parser.parse_args()

def dry_validate(manifest_path, env_id=None):
    """
    Dry validate the buildandburn.py script with a sample manifest file
    without actually creating infrastructure.
    """
    print_info("=" * 80)
    print_info("BUILD AND BURN - DRY VALIDATION")
    print_info("=" * 80)
    
    # Generate or use provided environment ID
    env_id = env_id or generate_env_id()
    print_info(f"Using environment ID: {env_id}")
    
    # Load manifest
    print_info(f"Loading manifest file: {manifest_path}")
    try:
        manifest = load_manifest(manifest_path)
        print_info("Manifest loaded successfully:")
        print(yaml.dump(manifest, default_flow_style=False))
    except Exception as e:
        print_error(f"Failed to load manifest file: {str(e)}")
        return False
    
    # Get project directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    terraform_dir = os.path.join(project_root, "terraform")
    
    # Create a temporary project directory
    project_dir = os.path.join(project_root, f"dry_run_{env_id}")
    print_info(f"Creating temporary project directory: {project_dir}")
    os.makedirs(project_dir, exist_ok=True)
    
    # Copy Terraform files to the project directory
    terraform_project_dir = os.path.join(project_dir, "terraform")
    print_info(f"Copying Terraform files to: {terraform_project_dir}")
    shutil.copytree(terraform_dir, terraform_project_dir, dirs_exist_ok=True)
    
    try:
        # Run pre-flight checks
        print_info("Running pre-flight checks...")
        run_preflight_checks(manifest, env_id, terraform_project_dir)
        
        # Prepare Terraform variables
        print_info("Preparing Terraform variables...")
        tf_vars = prepare_terraform_vars(manifest, env_id, project_dir)
        
        # Write variables to Terraform directory
        tf_vars_file = os.path.join(terraform_project_dir, "terraform.tfvars.json")
        with open(tf_vars_file, 'w') as f:
            json.dump(tf_vars, f, indent=2)
        
        print_info(f"Terraform variables file created: {tf_vars_file}")
        print_info("Terraform variables:")
        print(json.dumps(tf_vars, indent=2))
        
        # Validate Terraform modules against manifest
        print_info("Validating Terraform modules against manifest...")
        tf_modules_valid, validation_results = validate_terraform_modules_against_manifest(manifest, terraform_project_dir)
        
        # Print validation results
        print_info("\nDetailed Validation Results:")
        print(json.dumps(validation_results, indent=2))
        
        # If validation fails, try to fix the issues
        if not tf_modules_valid and validation_results.get("auto_fixable", False):
            print_info("Attempting to fix validation issues...")
            fixed = apply_terraform_module_fixes(validation_results, terraform_project_dir)
            if fixed:
                print_success("Successfully fixed validation issues!")
                # Re-validate to confirm fixes
                tf_modules_valid, validation_results = validate_terraform_modules_against_manifest(manifest, terraform_project_dir)
                print_info("Re-validation results:")
                print(json.dumps(validation_results, indent=2))
        
        # Generate resource summary
        print_info("Generating resource summary...")
        resources, cost_per_hour = generate_resource_summary(manifest, tf_vars, terraform_project_dir)
        
        print_info("\nResource Summary:")
        for resource in resources:
            print_info(f"- {resource['count']} x {resource['type']} ({resource['name']})")
        
        print_info(f"\nEstimated Cost: ${cost_per_hour}/hour (${cost_per_hour * 24 * 30}/month)")
        
        # Run terraform init
        print_info("\nInitializing Terraform (this will download providers but not create any resources)...")
        os.system(f"cd {terraform_project_dir} && terraform init -backend=false")
        
        # Run terraform validate
        print_info("\nValidating Terraform configuration...")
        validate_result = os.system(f"cd {terraform_project_dir} && terraform validate")
        if validate_result == 0:
            print_success("Terraform configuration is valid!")
        else:
            print_error("Terraform validation failed!")
            return False
        
        # Verify dependency recognition
        print_info("\nVerifying dependencies in manifest:")
        dependencies = []
        if 'dependencies' in manifest:
            for dep in manifest['dependencies']:
                dependencies.append(dep['type'])
        
        print_info(f"Dependencies found: {', '.join(dependencies)}")
        for dep in dependencies:
            print_info(f"Checking '{dep}' dependency:")
            if dep == "database":
                print_info("  - Database module would be created")
                print_info("  - RDS module would be created")
                print_info("  - EKS to RDS policy would be created")
            elif dep == "queue":
                print_info("  - Queue module would be created")
                print_info("  - MQ module would be created")
                print_info("  - EKS to MQ policy would be created")
            elif dep == "redis":
                print_info("  - Redis module would be created")
                print_info("  - ElastiCache module would be created")
                print_info("  - EKS to ElastiCache policy would be created")
        
        # Clean up
        print_info("\nCleaning up temporary files...")
        if "--keep-files" not in sys.argv:
            shutil.rmtree(project_dir)
            print_info(f"Removed temporary directory: {project_dir}")
        else:
            print_info(f"Temporary files kept at: {project_dir}")
        
        print_success("\nDry validation completed successfully!")
        return True
    
    except Exception as e:
        print_error(f"Error during dry validation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up on error if needed
        if os.path.exists(project_dir) and "--keep-files" not in sys.argv:
            shutil.rmtree(project_dir)

if __name__ == "__main__":
    args = parse_args()
    success = dry_validate(args.manifest, args.env_id)
    sys.exit(0 if success else 1) 