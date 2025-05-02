#!/usr/bin/env python3

import argparse
import os
import sys
import yaml
import json
import uuid
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
import glob
import re
import traceback
import random
import string
from datetime import datetime
import importlib.util

# Import version from __init__.py
try:
    from . import __version__
except ImportError:
    __version__ = "0.1.0"  # Default version if import fails

# Global configuration
CONFIG = {
    "TERRAFORM_APPLY_TIMEOUT": 7200,  # 2 hour timeout for terraform apply
    "TERRAFORM_DESTROY_TIMEOUT": 3600,  # 1 hour timeout for terraform destroy
    "TERRAFORM_INIT_TIMEOUT": 300,    # 5 minutes timeout for terraform init
    "PROGRESS_UPDATE_INTERVAL": 30,   # Update progress every 30 seconds
    "DEBUG": False
}

# Try to import the k8s_generator module if available
try:
    # First try to import from the same directory
    k8s_generator_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "k8s_generator.py")
    if os.path.exists(k8s_generator_path):
        spec = importlib.util.spec_from_file_location("k8s_generator", k8s_generator_path)
        k8s_generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(k8s_generator)
        print_info = lambda msg: None  # Dummy function to avoid undefined reference
        print_info("K8s generator module loaded successfully")
        k8s_generator_available = True
    else:
        k8s_generator_available = False
except Exception as e:
    print(f"Note: K8s generator module not loaded: {str(e)}")
    k8s_generator_available = False

def print_color(text, color_code):
    """Print text with color."""
    print(f"\033[{color_code}m{text}\033[0m")

def print_success(text):
    print_color(text, 92)  # Green

def print_info(text):
    print_color(text, 94)  # Blue

def print_warning(text):
    print_color(text, 93)  # Yellow

def print_error(text):
    print_color(text, 91)  # Red

def run_command(cmd, cwd=None, capture_output=False, allow_fail=False, env=None):
    """Run a command and return the process result."""
    print_info(f"Executing command: {cmd}")
    print_info(f"Working directory: {cwd}")
    
    if capture_output:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=not allow_fail,
                env=env
            )
            
            # Check for specific error codes
            if result.returncode == 127:  # Command not found
                if isinstance(cmd, list) and cmd:
                    command_name = cmd[0]
                else:
                    command_name = cmd.split()[0] if isinstance(cmd, str) else "command"
                
                print_error(f"Command '{command_name}' not found. Make sure it's installed and in your PATH.")
                
                # Check for some common commands and provide installation instructions
                if command_name == "terraform":
                    print_info("Terraform installation instructions: https://www.terraform.io/downloads.html")
                elif command_name == "kubectl":
                    print_info("kubectl installation instructions: https://kubernetes.io/docs/tasks/tools/")
                elif command_name == "aws":
                    print_info("AWS CLI installation instructions: https://aws.amazon.com/cli/")
                
                # Provide user's PATH for debugging
                print_info(f"Current PATH: {os.environ.get('PATH', 'Not available')}")
                
                if allow_fail:
                    return result
                else:
                    raise FileNotFoundError(f"Command '{command_name}' not found")
            
            return result
        except subprocess.CalledProcessError as e:
            if allow_fail:
                return e
            print_error(f"Failed to execute command: {e}")
            print_error(f"Command was: {cmd}")
            print_error(f"Working directory: {cwd}")
            if e.output:
                print_error(f"Output: {e.output}")
            if e.stderr:
                print_error(f"Error: {e.stderr}")
            raise
        except Exception as e:
            if allow_fail:
                # Create a subprocess-like result object
                class ErrorResult:
                    def __init__(self, exception):
                        self.returncode = 1
                        self.exception = exception
                        self.stdout = ""
                        self.stderr = str(exception)
                
                return ErrorResult(e)
            print_error(f"Exception running command: {str(e)}")
            print_error(f"Command was: {cmd}")
            print_error(f"Working directory: {cwd}")
            raise
    else:
        try:
            # For non-captured output, use Popen to stream output in real-time
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                shell=isinstance(cmd, str),
                env=env
            )
            returncode = process.wait()
            
            if returncode == 127:  # Command not found
                if isinstance(cmd, list) and cmd:
                    command_name = cmd[0]
                else:
                    command_name = cmd.split()[0] if isinstance(cmd, str) else "command"
                
                print_error(f"Command '{command_name}' not found. Make sure it's installed and in your PATH.")
                
                # Provide installation instructions
                if command_name == "terraform":
                    print_info("Terraform installation instructions: https://www.terraform.io/downloads.html")
                elif command_name == "kubectl":
                    print_info("kubectl installation instructions: https://kubernetes.io/docs/tasks/tools/")
                elif command_name == "aws":
                    print_info("AWS CLI installation instructions: https://aws.amazon.com/cli/")
                
                if allow_fail:
                    return returncode
                else:
                    raise FileNotFoundError(f"Command '{command_name}' not found")
            
            if returncode != 0 and not allow_fail:
                raise subprocess.CalledProcessError(returncode, cmd)
            
            return returncode
        except Exception as e:
            if allow_fail:
                return 1
            print_error(f"Exception running command: {str(e)}")
            print_error(f"Command was: {cmd}")
            print_error(f"Working directory: {cwd}")
            raise

def is_terraform_installed():
    """Check if Terraform is installed and available in the PATH."""
    try:
        result = subprocess.run(
            ["terraform", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            version_match = re.search(r'Terraform v(\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                version = version_match.group(1)
                print_info(f"Terraform version {version} found.")
                return True
            return True
        else:
            print_warning("Terraform command found but returned an error.")
            if result.stderr:
                print_warning(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print_warning("Terraform command not found in PATH.")
        # Check in common installation directories
        common_paths = [
            "/usr/local/bin/terraform",
            "/usr/bin/terraform",
            "/opt/homebrew/bin/terraform",
            os.path.expanduser("~/bin/terraform"),
            os.path.expanduser("~/.local/bin/terraform")
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print_info(f"Terraform found at {path} but not in your PATH.")
                print_info(f"Add the directory to your PATH or use the full path to the executable.")
                return False
        
        print_warning("Terraform not found in common installation directories.")
        print_info("Please install Terraform from: https://www.terraform.io/downloads.html")
        return False
    except Exception as e:
        print_warning(f"Error checking Terraform installation: {str(e)}")
        return False

def is_kubectl_installed():
    """Check if kubectl is installed and available in the PATH."""
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            version_output = result.stdout if result.stdout else result.stderr
            version_match = re.search(r'Client Version: .*?v(\d+\.\d+\.\d+)', version_output)
            if version_match:
                version = version_match.group(1)
                print_info(f"kubectl version {version} found.")
                return True
            return True
        else:
            print_warning("kubectl command found but returned an error.")
            if result.stderr:
                print_warning(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print_warning("kubectl command not found in PATH.")
        # Check in common installation directories
        common_paths = [
            "/usr/local/bin/kubectl",
            "/usr/bin/kubectl",
            "/opt/homebrew/bin/kubectl",
            os.path.expanduser("~/bin/kubectl"),
            os.path.expanduser("~/.local/bin/kubectl")
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print_info(f"kubectl found at {path} but not in your PATH.")
                print_info(f"Add the directory to your PATH or use the full path to the executable.")
                return False
        
        print_warning("kubectl not found in common installation directories.")
        print_info("Please install kubectl from: https://kubernetes.io/docs/tasks/tools/")
        return False
    except Exception as e:
        print_warning(f"Error checking kubectl installation: {str(e)}")
        return False

def is_aws_cli_installed():
    """Check if AWS CLI is installed and available in the PATH."""
    try:
        result = subprocess.run(
            ["aws", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            version_output = result.stdout if result.stdout else result.stderr
            version_match = re.search(r'aws-cli/(\d+\.\d+\.\d+)', version_output)
            if version_match:
                version = version_match.group(1)
                print_info(f"AWS CLI version {version} found.")
                return True
            return True
        else:
            print_warning("AWS CLI command found but returned an error.")
            if result.stderr:
                print_warning(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print_warning("AWS CLI command not found in PATH.")
        # Check in common installation directories
        common_paths = [
            "/usr/local/bin/aws",
            "/usr/bin/aws",
            "/opt/homebrew/bin/aws",
            os.path.expanduser("~/bin/aws"),
            os.path.expanduser("~/.local/bin/aws")
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print_info(f"AWS CLI found at {path} but not in your PATH.")
                print_info(f"Add the directory to your PATH or use the full path to the executable.")
                return False
        
        print_warning("AWS CLI not found in common installation directories.")
        print_info("Please install AWS CLI from: https://aws.amazon.com/cli/")
        return False
    except Exception as e:
        print_warning(f"Error checking AWS CLI installation: {str(e)}")
        return False

def check_prerequisites():
    """Check if required tools are installed."""
    print_color("\n===============================================================================", "34")
    print_color("CHECKING PREREQUISITES", "34")
    print_color("===============================================================================", "34")
    
    prerequisites_ok = True
    missing_tools = []
    
    # Check Terraform
    if not is_terraform_installed():
        prerequisites_ok = False
        missing_tools.append("terraform")
        print_error("Terraform is required but not found.")
        print_info("Please install Terraform from: https://www.terraform.io/downloads.html")
    
    # Check AWS CLI
    if not is_aws_cli_installed():
        prerequisites_ok = False
        missing_tools.append("aws-cli")
        print_error("AWS CLI is required but not found.")
        print_info("Please install AWS CLI from: https://aws.amazon.com/cli/")
    
    # Check kubectl
    if not is_kubectl_installed():
        prerequisites_ok = False
        missing_tools.append("kubectl")
        print_error("kubectl is required but not found.")
        print_info("Please install kubectl from: https://kubernetes.io/docs/tasks/tools/")
    
    # Summary and confirmation
    if not prerequisites_ok:
        print_color("\n===============================================================================", "31")
        print_error(f"MISSING PREREQUISITES: {', '.join(missing_tools)}")
        print_color("===============================================================================", "31")
        
        # Check if we should prompt for continuation
        if os.environ.get('BUILDANDBURN_IGNORE_MISSING_PREREQUISITES') == '1':
            print_warning("Ignoring missing prerequisites due to BUILDANDBURN_IGNORE_MISSING_PREREQUISITES=1")
            return True
        
        # Ask user if they want to continue anyway
        try:
            response = input("Continue anyway? This may lead to errors later. (y/N): ").strip().lower()
            if response == 'y' or response == 'yes':
                print_warning("Continuing despite missing prerequisites. Expect errors.")
                return True
            else:
                print_info("Aborting due to missing prerequisites.")
                sys.exit(1)
        except KeyboardInterrupt:
            print_info("\nAborted.")
            sys.exit(1)
    else:
        print_success("All prerequisites are installed.")
    
    return prerequisites_ok

def load_manifest(manifest_path):
    """Load the manifest file."""
    try:
        with open(manifest_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print_error(f"Failed to load manifest file: {e}")
        sys.exit(1)

def generate_env_id():
    """Generate a unique environment ID."""
    return str(uuid.uuid4())[:8]

def prepare_terraform_vars(manifest, env_id, project_dir):
    """Prepare Terraform variables based on the manifest."""
    # Extract dependencies from manifest
    dependencies = []
    if 'dependencies' in manifest:
        for dep in manifest['dependencies']:
            dependencies.append(dep['type'])
    
    print_info(f"Detected dependencies: {', '.join(dependencies) if dependencies else 'none'}")
    
    # Create terraform.tfvars.json file
    tf_vars = {
        "project_name": manifest['name'],
        "env_id": env_id,
        "region": manifest.get('region', 'us-west-2'),
        "dependencies": dependencies,
        # Add required variables with defaults to prevent errors
        "vpc_cidr": "10.0.0.0/16",
        "eks_instance_types": ["t3.medium"],
        "eks_node_min": 1,
        "eks_node_max": 3,
        "k8s_version": "1.27"
    }
    
    # Add database-specific variables if needed
    if 'database' in dependencies:
        db_config = next((d for d in manifest['dependencies'] if d['type'] == 'database'), None)
        if db_config:
            tf_vars.update({
                "db_engine": db_config.get('provider', 'postgres'),
                "db_engine_version": db_config.get('version', '13'),
                "db_instance_class": db_config.get('instance_class', 'db.t3.small'),
                "db_allocated_storage": int(db_config.get('storage', 20)),
            })
        else:
            print_warning("Database dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "db_engine": "postgres",
                "db_engine_version": "13",
                "db_instance_class": "db.t3.small",
                "db_allocated_storage": 20,
            })
    
    # Add queue-specific variables if needed
    if 'queue' in dependencies:
        mq_config = next((d for d in manifest['dependencies'] if d['type'] == 'queue'), None)
        if mq_config:
            tf_vars.update({
                "mq_engine_type": mq_config.get('provider', 'RabbitMQ'),
                "mq_engine_version": mq_config.get('version', '3.13'),
                "mq_instance_type": mq_config.get('instance_class', 'mq.t3.micro'),
            })
        else:
            print_warning("Queue dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "mq_engine_type": "RabbitMQ",
                "mq_engine_version": "3.13",
                "mq_instance_type": "mq.t3.micro",
            })
    
    # Add Redis-specific variables if needed
    if 'redis' in dependencies:
        redis_config = next((d for d in manifest['dependencies'] if d['type'] == 'redis'), None)
        if redis_config:
            tf_vars.update({
                "redis_node_type": redis_config.get('node_type', 'cache.t3.micro'),
                "redis_engine_version": redis_config.get('version', '6.2'),
                "redis_cluster_size": int(redis_config.get('cluster_size', 1)),
                "redis_auth_enabled": redis_config.get('auth_enabled', True),
                "redis_multi_az_enabled": redis_config.get('multi_az', False),
            })
        else:
            print_warning("Redis dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "redis_node_type": "cache.t3.micro",
                "redis_engine_version": "6.2",
                "redis_cluster_size": 1,
                "redis_auth_enabled": True,
                "redis_multi_az_enabled": False,
            })
    
    return tf_vars

def run_preflight_checks(manifest, env_id, terraform_project_dir):
    """Run pre-flight checks to ensure the script can proceed safely."""
    print_info("=" * 80)
    print_info("RUNNING PRE-FLIGHT CHECKS")
    print_info("=" * 80)
    
    checks_passed = True
    
    # Check if AWS CLI is configured correctly
    print_info("Checking AWS CLI configuration...")
    try:
        # Check AWS CLI version
        aws_version = subprocess.run(["aws", "--version"], 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                    text=True, check=True)
        print_info(f"AWS CLI: {aws_version.stdout.strip() or aws_version.stderr.strip()}")
        
        # Check AWS identity
        aws_identity = subprocess.run(["aws", "sts", "get-caller-identity"], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                     text=True, check=True)
        print_info("AWS Identity check passed")
        
        # Check AWS region
        aws_region = os.environ.get('AWS_REGION', manifest.get('region', 'us-west-2'))
        print_info(f"Using AWS region: {aws_region}")
        
        # Check if AWS region is valid
        aws_regions = subprocess.run(["aws", "ec2", "describe-regions", "--query", "Regions[].RegionName", "--output", "text"], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, check=True)
        regions_list = aws_regions.stdout.strip().split()
        if aws_region not in regions_list:
            print_warning(f"Region {aws_region} may not be valid or enabled for your account")
            print_warning(f"Available regions: {', '.join(regions_list[:5])}...")
            checks_passed = False
    except Exception as e:
        print_error(f"AWS CLI check failed: {str(e)}")
        checks_passed = False
    
    # Check Terraform configuration
    print_info("Checking Terraform configuration...")
    try:
        # Check Terraform version
        tf_version = subprocess.run(["terraform", "--version"], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                 text=True, check=True)
        print_info(f"Terraform: {tf_version.stdout.strip().split('\\n')[0]}")
        
        # Check for required Terraform files
        required_files = ["main.tf", "variables.tf"]
        for file in required_files:
            if not os.path.exists(os.path.join(terraform_project_dir, file)):
                print_error(f"Required Terraform file {file} not found")
                checks_passed = False
        
        # Check for modules
        required_modules = ["vpc", "eks"]
        modules_dir = os.path.join(terraform_project_dir, "modules")
        if not os.path.exists(modules_dir):
            print_error("Terraform modules directory not found")
            checks_passed = False
        else:
            for module in required_modules:
                if not os.path.exists(os.path.join(modules_dir, module)):
                    print_error(f"Required Terraform module {module} not found")
                    checks_passed = False
    except Exception as e:
        print_error(f"Terraform check failed: {str(e)}")
        checks_passed = False
    
    # Check kubectl
    print_info("Checking kubectl...")
    try:
        kubectl_version = subprocess.run(["kubectl", "version", "--client", "--output=yaml"], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                     text=True, check=True)
        print_info(f"kubectl client detected")
    except Exception as e:
        print_error(f"kubectl check failed: {str(e)}")
        checks_passed = False
    
    # Check Helm
    print_info("Checking Helm...")
    try:
        helm_version = subprocess.run(["helm", "version", "--short"], 
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                   text=True, check=True)
        print_info(f"Helm: {helm_version.stdout.strip()}")
    except Exception as e:
        print_error(f"Helm check failed: {str(e)}")
        checks_passed = False
    
    # Print summary
    if checks_passed:
        print_success("All pre-flight checks passed!")
    else:
        print_warning("Some pre-flight checks failed. Proceed with caution or fix the issues before continuing.")
        # Ask for confirmation to continue
        try:
            if input("Do you want to continue anyway? (y/N): ").lower() != 'y':
                print_info("Aborting deployment")
                sys.exit(0)
        except KeyboardInterrupt:
            print_info("\nAborting deployment")
            sys.exit(0)
    
    return checks_passed

def setup_cleanup_handler(project_dir, terraform_project_dir):
    """Set up a cleanup handler for graceful shutdown on interruption."""
    import atexit
    import signal
    
    # Flag to track if we're already exiting to avoid multiple exit calls
    is_exiting = False
    
    def cleanup_handler(signum=None, frame=None):
        nonlocal is_exiting
        
        # Avoid running cleanup multiple times
        if is_exiting:
            return
        is_exiting = True
        
        print_info("\n")
        print_info("=" * 80)
        print_info("CLEANING UP RESOURCES")
        print_info("=" * 80)
        
        # Check if terraform state exists
        state_file = os.path.join(terraform_project_dir, "terraform.tfstate")
        if os.path.exists(state_file):
            print_info("Found Terraform state file. Resources may have been created.")
            print_info("You might want to run 'terraform destroy' to clean up any created resources.")
            print_info(f"Terraform directory: {terraform_project_dir}")
            
            # Save terraform directory path to a file for reference
            with open(os.path.join(os.path.expanduser("~"), ".buildandburn_last"), "w") as f:
                f.write(terraform_project_dir)
            
            print_info(f"Reference saved to ~/.buildandburn_last")
        
        print_info("Exiting...")
        
        # Only call sys.exit if this wasn't called from an atexit handler
        if signum is not None:
            sys.exit(1)
    
    # Register the cleanup handler for various signals
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    # Register with atexit for normal exits
    atexit.register(cleanup_handler)
    
    return cleanup_handler

def validate_terraform_configuration(terraform_project_dir):
    """
    Validate the Terraform configuration and format files.
    Returns (True, None) if validation succeeds, (False, error_message) otherwise.
    """
    print_color("\n===============================================================================", "34")
    print_color("VALIDATING TERRAFORM CONFIGURATION", "34")
    print_color("================================================================================", "34")
    
    # First check if terraform is actually installed and accessible
    if not is_terraform_installed():
        print_error("Terraform command not found. Please make sure Terraform is installed and available in your PATH.")
        print_info("You can download Terraform from: https://www.terraform.io/downloads.html")
        return False, "Terraform not installed"
    
    # Checking for Terraform files in the directory
    tf_files = glob.glob(f"{terraform_project_dir}/**/*.tf", recursive=True)
    print_info(f"Checking Terraform files...")
    print_info(f"Found {len(tf_files)} Terraform files.")
    
    # Debug: Print the first few files found to verify path
    debug_log_path = os.path.join(terraform_project_dir, "terraform_validate_debug.log")
    with open(debug_log_path, 'w') as debug_log:
        debug_log.write(f"Terraform directory: {terraform_project_dir}\n\n")
        debug_log.write(f"Found {len(tf_files)} Terraform files:\n")
        for i, tf_file in enumerate(tf_files[:5]):  # Print first 5 files
            debug_log.write(f"{i+1}. {tf_file}\n")
        if len(tf_files) > 5:
            debug_log.write(f"... and {len(tf_files) - 5} more.\n\n")
    
    # Step 1: Check if formatting is correct using 'terraform fmt -check -recursive'
    fmt_cmd = ["terraform", "fmt", "-check", "-recursive"]
    try:
        fmt_result = run_command(fmt_cmd, cwd=terraform_project_dir, capture_output=True, allow_fail=True)
        if fmt_result.returncode != 0:
            print_warning("Terraform files have formatting issues.")
            
            # Auto-format
            print_info("Automatically formatting Terraform files...")
            auto_fmt_cmd = ["terraform", "fmt", "-recursive"]
            fmt_fix_result = run_command(auto_fmt_cmd, cwd=terraform_project_dir, capture_output=True, allow_fail=True)
            if fmt_fix_result.returncode == 0:
                print_success("Terraform files have been automatically formatted.")
            else:
                print_warning("Failed to format Terraform files. You can manually fix formatting with: terraform fmt -recursive")
        else:
            print_success("Terraform files are properly formatted.")
    except Exception as e:
        print_warning(f"Unable to check Terraform formatting: {str(e)}")
    
    # Step 2: Run standard Terraform validation
    print_info("Running standard validation...")
    validate_cmd = ["terraform", "validate"]
    try:
        # Run terraform validate and capture output
        result = subprocess.run(
            validate_cmd,
            cwd=terraform_project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        # Log validation results for debugging
        with open(debug_log_path, 'a') as debug_log:
            debug_log.write("\nValidation Command: terraform validate\n")
            debug_log.write(f"Return code: {result.returncode}\n")
            debug_log.write("Standard output:\n")
            debug_log.write(result.stdout or "(none)\n")
            debug_log.write("\nStandard error:\n")
            debug_log.write(result.stderr or "(none)\n")
        
        # Check for successful validation
        if result.returncode == 0:
            # Print output for transparency
            if result.stdout:
                print(result.stdout.strip())
            
            print_success("Terraform validation succeeded!")
            return True, None
        else:
            # Handle validation failure
            print_error("Terraform validation failed:")
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
            
            print_info(f"Debug log written to: {debug_log_path}")
            error_msg = result.stderr if result.stderr else "Unknown validation error"
            return False, error_msg
    except Exception as e:
        print_error(f"Error validating Terraform configuration: {str(e)}")
        traceback.print_exc()
        return False, str(e)

def generate_resource_summary(manifest, tf_vars, terraform_project_dir):
    """Generate a summary of resources to be provisioned and estimated costs."""
    print_info("=" * 80)
    print_info("RESOURCE SUMMARY")
    print_info("=" * 80)
    
    # Default resource costs (very rough estimates)
    resource_costs = {
        "eks_cluster": 0.10,  # $/hour for EKS control plane
        "ec2_instance": {
            "t3.medium": 0.0416,  # $/hour
            "t3.large": 0.0832,   # $/hour
            "t3.xlarge": 0.1664,  # $/hour
        },
        "rds_instance": {
            "db.t3.small": 0.034,   # $/hour
            "db.t3.medium": 0.068,  # $/hour
            "db.t3.large": 0.136,   # $/hour
        },
        "mq_instance": {
            "mq.t3.micro": 0.028,   # $/hour
            "mq.t3.small": 0.056,   # $/hour
        }
    }
    
    total_cost_per_hour = 0
    resources = []
    
    # EKS Cluster
    resources.append({
        "type": "EKS Cluster",
        "name": f"{tf_vars['project_name']}-{tf_vars['env_id']}",
        "count": 1,
        "cost_per_hour": resource_costs["eks_cluster"]
    })
    total_cost_per_hour += resource_costs["eks_cluster"]
    
    # EC2 Instances for EKS
    node_min = tf_vars.get("eks_node_min", 1)
    instance_types = tf_vars.get("eks_instance_types", ["t3.medium"])
    instance_type = instance_types[0] if instance_types else "t3.medium"
    instance_cost = resource_costs["ec2_instance"].get(instance_type, 0.05)
    resources.append({
        "type": "EC2 Instance",
        "name": f"eks-node-{instance_type}",
        "count": node_min,
        "cost_per_hour": instance_cost * node_min
    })
    total_cost_per_hour += instance_cost * node_min
    
    # RDS Instance (if requested)
    if "database" in tf_vars.get("dependencies", []):
        db_instance_class = tf_vars.get("db_instance_class", "db.t3.small")
        db_cost = resource_costs["rds_instance"].get(db_instance_class, 0.04)
        resources.append({
            "type": "RDS Instance",
            "name": f"{tf_vars['project_name']}-db",
            "count": 1,
            "cost_per_hour": db_cost
        })
        total_cost_per_hour += db_cost
    
    # MQ Instance (if requested)
    if "queue" in tf_vars.get("dependencies", []):
        mq_instance_type = tf_vars.get("mq_instance_type", "mq.t3.micro")
        mq_cost = resource_costs["mq_instance"].get(mq_instance_type, 0.03)
        resources.append({
            "type": "MQ Instance",
            "name": f"{tf_vars['project_name']}-mq",
            "count": 1, 
            "cost_per_hour": mq_cost
        })
        total_cost_per_hour += mq_cost
    
    # Print resources table
    print_info(f"{'Resource Type':<20} {'Name':<30} {'Count':<10} {'Est. Cost/Hour':<15}")
    print_info("-" * 75)
    for resource in resources:
        print_info(
            f"{resource['type']:<20} "
            f"{resource['name']:<30} "
            f"{resource['count']:<10} "
            f"${resource['cost_per_hour']:.2f}/hr"
        )
    print_info("-" * 75)
    print_info(f"{'Total Estimated Cost':<60} ${total_cost_per_hour:.2f}/hr")
    print_info(f"{'Monthly Estimate (30 days)':<60} ${total_cost_per_hour * 24 * 30:.2f}")
    
    print_warning("Cost estimates are approximate and may vary based on AWS pricing changes and actual usage.")
    print_warning("Additional costs may be incurred for data transfer, storage, and other AWS services.")
    
    return resources, total_cost_per_hour

def provision_infrastructure(manifest, env_id, terraform_dir, args=None):
    """Provision infrastructure using Terraform based on the manifest."""
    # Default auto_approve
    if args is None:
        class DefaultArgs:
            auto_approve = False
            skip_module_confirmation = False
        args = DefaultArgs()
        
    print_info("=" * 80)
    print_info("PROVISIONING INFRASTRUCTURE")
    print_info("=" * 80)
    print_info(f"Environment ID: {env_id}")
    print_info(f"Project name: {manifest['name']}")
    print_info(f"Region: {manifest.get('region', 'us-west-2')}")
    print_info(f"Terraform directory: {terraform_dir}")
    
    # Create a project directory
    project_dir = os.path.join(os.path.expanduser("~"), ".buildandburn", env_id)
    print_info(f"Creating project directory: {project_dir}")
    os.makedirs(project_dir, exist_ok=True)
    
    # Copy Terraform files to project directory
    terraform_project_dir = os.path.join(project_dir, "terraform")
    print_info(f"Copying Terraform files to: {terraform_project_dir}")
    shutil.copytree(terraform_dir, terraform_project_dir, dirs_exist_ok=True)
    
    # Create state directory inside the terraform directory
    state_dir = os.path.join(terraform_project_dir, "state")
    os.makedirs(state_dir, exist_ok=True)
    state_file_path = os.path.join(state_dir, "terraform.tfstate")
    
    # Create a backend override file to ensure all components use the same state file
    backend_file = os.path.join(terraform_project_dir, "backend_override.tf")
    print_info(f"Creating backend override file: {backend_file}")
    with open(backend_file, 'w') as f:
        f.write(f"""
# Override backend to use a single state file for all components
terraform {{
  backend "local" {{
    path = "{state_file_path}"
  }}
}}
""")
    
    # Set up cleanup handler for graceful interruption
    cleanup_handler = setup_cleanup_handler(project_dir, terraform_project_dir)
    
    # Run pre-flight checks
    run_preflight_checks(manifest, env_id, terraform_project_dir)
    
    # Verify AWS credentials
    print_info("Verifying AWS credentials...")
    try:
        aws_output = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        account_id = aws_output.stdout.strip()
        print_info(f"Using AWS Account: {account_id}")
    except Exception as e:
        print_error(f"AWS credentials verification failed: {str(e)}")
        print_error("Please configure AWS credentials with 'aws configure' and try again.")
        return project_dir, {}
    
    # Check AWS region
    region = manifest.get('region', 'us-west-2')
    if os.environ.get('AWS_REGION'):
        print_info(f"Using AWS region from environment: {os.environ.get('AWS_REGION')}")
    else:
        print_info(f"Setting AWS region to: {region}")
        os.environ['AWS_REGION'] = region
    
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
    
    # Validate Terraform modules against manifest requirements
    tf_modules_valid, validation_results = validate_terraform_modules_against_manifest(manifest, terraform_project_dir)
    
    # If validation fails because of missing core modules, stop execution
    if not tf_modules_valid and validation_results.get("modules", {}).get("missing"):
        print_error("Terraform modules validation failed. The required core modules for this deployment are not available.")
        print_info("\nDetailed Validation Results:")
        print(json.dumps(validation_results, indent=2))
        
        print_info("\nNext Steps:")
        for i, step in enumerate(validation_results.get("next_steps", [])):
            print_info(f"{i+1}. {step}")
        
        # Save validation results to file
        validation_file = os.path.join(project_dir, "terraform_validation_results.json")
        with open(validation_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        print_info(f"\nValidation results saved to: {validation_file}")
        print_info("Please fix the issues and try again.")
        
        return project_dir, {}
    
    # Check for missing policy modules and prompt for confirmation
    missing_policy_modules = validation_results.get("policy_modules", {}).get("missing", [])
    missing_access_policy_modules = validation_results.get("access_policy_modules", {}).get("missing", [])
    
    if (missing_policy_modules or missing_access_policy_modules) and (not hasattr(args, 'skip_module_confirmation') or not args.skip_module_confirmation):
        if missing_policy_modules:
            print_warning("\nThe following policy modules are missing but might be needed for your deployment:")
            for module in missing_policy_modules:
                print_warning(f"- {module}")
        
        if missing_access_policy_modules:
            print_warning("\nThe following access policy modules are missing but might be needed for your deployment:")
            for module in missing_access_policy_modules:
                print_warning(f"- {module}")
        
        print_warning("\nMissing policy modules may result in connectivity issues between services.")
        
        if hasattr(args, 'auto_approve') and args.auto_approve:
            print_info("Auto-approve enabled, continuing despite missing policy modules.")
        else:
            if input("\nDo you want to continue with missing policy modules? (y/N): ").lower() != 'y':
                print_info("Deployment aborted by user due to missing policy modules.")
                return project_dir, {}
    
    # If validation identified missing policy modules that can be auto-fixed, try to fix them
    if validation_results.get("auto_fixable", False) and validation_results.get("fix_actions"):
        print_info("\nAttempting to automatically fix missing policy modules...")
        
        # Copy missing policy modules from the original terraform dir to the project dir if they exist
        original_modules_dir = os.path.join(terraform_dir, "modules")
        project_modules_dir = os.path.join(terraform_project_dir, "modules")
        
        # Copy missing standard policy modules
        for policy_module in missing_policy_modules:
            original_module_path = os.path.join(original_modules_dir, policy_module)
            project_module_path = os.path.join(project_modules_dir, policy_module)
            
            if os.path.exists(original_module_path) and not os.path.exists(project_module_path):
                print_info(f"Copying {policy_module} module from original terraform directory...")
                shutil.copytree(original_module_path, project_module_path)
                print_success(f"Copied {policy_module} module to project terraform directory")
        
        # Copy missing access policy modules
        for access_policy_module in missing_access_policy_modules:
            original_module_path = os.path.join(original_modules_dir, access_policy_module)
            project_module_path = os.path.join(project_modules_dir, access_policy_module)
            
            if os.path.exists(original_module_path) and not os.path.exists(project_module_path):
                print_info(f"Copying {access_policy_module} module from original terraform directory...")
                shutil.copytree(original_module_path, project_module_path)
                print_success(f"Copied {access_policy_module} module to project terraform directory")
        
        # Apply fixes to main.tf
        fixed = apply_terraform_module_fixes(validation_results, terraform_project_dir)
        
        if fixed:
            print_success("Successfully fixed missing policy modules!")
            
            # Re-validate to confirm fixes
            print_info("Re-validating Terraform modules after fixes...")
            tf_modules_valid, validation_results = validate_terraform_modules_against_manifest(manifest, terraform_project_dir)
        else:
            print_warning("Could not automatically fix all policy module issues. Continuing anyway...")
    
    # Generate resource summary and cost estimates
    resources, cost_per_hour = generate_resource_summary(manifest, tf_vars, terraform_project_dir)
    
    # Initialize Terraform with provider verification
    print_info("=" * 80)
    print_info("INITIALIZING TERRAFORM")
    print_info("=" * 80)
    try:
        # Check if main.tf already contains provider configurations
        main_tf_path = os.path.join(terraform_project_dir, "main.tf")
        providers_already_defined = False
        
        if os.path.exists(main_tf_path):
            with open(main_tf_path, 'r') as f:
                main_tf_content = f.read()
                if 'provider "aws"' in main_tf_content:
                    print_info("AWS provider already defined in main.tf")
                    providers_already_defined = True
        
        # Remove providers.tf if it exists to avoid duplicate providers
        providers_file = os.path.join(terraform_project_dir, "providers.tf")
        if os.path.exists(providers_file):
            print_info("Removing existing providers.tf to avoid duplicates")
            os.remove(providers_file)
        
        # Only create providers.tf if providers aren't already defined
        if not providers_already_defined:
            print_info("Creating providers.tf file...")
            with open(providers_file, 'w') as f:
                f.write(f"""
provider "aws" {{
  region = "{region}"
}}

terraform {{
  required_version = ">= 1.0.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }}
    kubernetes = {{
      source  = "hashicorp/kubernetes"
      version = "~> 2.10"
    }}
    helm = {{
      source  = "hashicorp/helm"
      version = "~> 2.5"
    }}
  }}
}}
""")
        
        # Remove any existing Terraform state
        print_info("Removing any existing Terraform state...")
        state_files = glob.glob(os.path.join(terraform_project_dir, "*.tfstate*"))
        for state_file in state_files:
            os.remove(state_file)
        
        # Run terraform init with explicit backend config
        print_info("Running terraform init with explicit backend configuration...")
        run_command(f"terraform init -reconfigure", cwd=terraform_project_dir)
        
        # Verify state file location
        state_file_path = os.path.join(state_dir, "terraform.tfstate")
        if os.path.exists(state_file_path):
            # Check if state file is valid and fix if needed
            if ensure_valid_state_file(state_file_path, terraform_project_dir):
                print_info("Existing state file was invalid and has been fixed.")
            else:
                print_success(f"Existing state file at {state_file_path} is valid.")
        else:
            # Create a properly formatted empty state file
            create_valid_state_file(state_file_path, terraform_project_dir)
        
        # Save state file location in environment info
        env_info_file = os.path.join(project_dir, "env_info.json")
        env_info = {
            "env_id": env_id,
            "project_name": manifest['name'],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "state_file": state_file_path,
            "terraform_dir": terraform_project_dir,
            "region": region
        }
        with open(env_info_file, 'w') as f:
            json.dump(env_info, f, indent=2)
    except Exception as e:
        print_error(f"Terraform initialization failed: {str(e)}")
        print_warning("Attempting to fix common issues...")
        
        # Clean terraform directory and try again
        print_info("Cleaning Terraform directory and reinitializing...")
        shutil.rmtree(os.path.join(terraform_project_dir, ".terraform"), ignore_errors=True)
        for f in glob.glob(os.path.join(terraform_project_dir, ".terraform.lock.hcl")):
            os.remove(f)
        
        # Try initialization with plugin cache
        plugin_cache_dir = os.path.join(os.path.expanduser("~"), ".terraform.d", "plugin-cache")
        os.makedirs(plugin_cache_dir, exist_ok=True)
        os.environ["TF_PLUGIN_CACHE_DIR"] = plugin_cache_dir
        
        try:
            run_command("terraform init -reconfigure", cwd=terraform_project_dir)
        except Exception as e2:
            print_error(f"Terraform reinitialization failed: {str(e2)}")
            return project_dir, {}
    
    # Validate Terraform configuration
    validation_success, error_msg = validate_terraform_configuration(terraform_project_dir)
    if not validation_success:
        print_error("Terraform validation failed.")
        print_info("You can try to fix the validation errors and run the script again.")
        print_info("Common solutions include:")
        print_info("1. Check that all required variables are defined")
        print_info("2. Ensure provider versions are compatible")
        print_info("3. Verify that all referenced modules exist")
        
        # Ask the user if they want to continue anyway despite validation failure
        try:
            response = input("Do you want to continue anyway? This is risky and may lead to errors (y/N): ").strip().lower()
            if response != 'y' and response != 'yes':
                print_info("Exiting due to validation failure.")
                # Instead of sys.exit, return empty values
                return project_dir, {}
            print_warning("Continuing despite validation failure. Proceed with caution.")
        except KeyboardInterrupt:
            print_info("\nAborted.")
            return project_dir, {}
    
    # Run terraform init
    print_info("Initializing Terraform...")
    print_info("=" * 80)
    print_info("INITIALIZING TERRAFORM")
    print_info("=" * 80)
    try:
        # Check if main.tf already contains provider configurations
        main_tf_path = os.path.join(terraform_project_dir, "main.tf")
        providers_already_defined = False
        
        if os.path.exists(main_tf_path):
            with open(main_tf_path, 'r') as f:
                main_tf_content = f.read()
                if 'provider "aws"' in main_tf_content:
                    print_info("AWS provider already defined in main.tf")
                    providers_already_defined = True
        
        # Remove providers.tf if it exists to avoid duplicate providers
        providers_file = os.path.join(terraform_project_dir, "providers.tf")
        if os.path.exists(providers_file):
            print_info("Removing existing providers.tf to avoid duplicates")
            os.remove(providers_file)
        
        # Only create providers.tf if providers aren't already defined
        if not providers_already_defined:
            print_info("Creating providers.tf file...")
            with open(providers_file, 'w') as f:
                f.write(f"""
provider "aws" {{
  region = "{region}"
}}

terraform {{
  required_version = ">= 1.0.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }}
    kubernetes = {{
      source  = "hashicorp/kubernetes"
      version = "~> 2.10"
    }}
    helm = {{
      source  = "hashicorp/helm"
      version = "~> 2.5"
    }}
  }}
}}
""")
        
        # Remove any existing Terraform state
        print_info("Removing any existing Terraform state...")
        state_files = glob.glob(os.path.join(terraform_project_dir, "*.tfstate*"))
        for state_file in state_files:
            os.remove(state_file)
        
        # Run terraform init with explicit backend config
        print_info("Running terraform init with explicit backend configuration...")
        run_command(f"terraform init -reconfigure", cwd=terraform_project_dir)
        
        # Verify state file location
        state_file_path = os.path.join(state_dir, "terraform.tfstate")
        if os.path.exists(state_file_path):
            # Check if state file is valid and fix if needed
            if ensure_valid_state_file(state_file_path, terraform_project_dir):
                print_info("Existing state file was invalid and has been fixed.")
            else:
                print_success(f"Existing state file at {state_file_path} is valid.")
        else:
            # Create a properly formatted empty state file
            create_valid_state_file(state_file_path, terraform_project_dir)
        
        # Save state file location in environment info
        env_info_file = os.path.join(project_dir, "env_info.json")
        env_info = {
            "env_id": env_id,
            "project_name": manifest['name'],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "state_file": state_file_path,
            "terraform_dir": terraform_project_dir,
            "region": region
        }
        with open(env_info_file, 'w') as f:
            json.dump(env_info, f, indent=2)
    except Exception as e:
        print_error(f"Terraform initialization failed: {str(e)}")
        print_warning("Attempting to fix common issues...")
        
        # Clean terraform directory and try again
        print_info("Cleaning Terraform directory and reinitializing...")
        shutil.rmtree(os.path.join(terraform_project_dir, ".terraform"), ignore_errors=True)
        for f in glob.glob(os.path.join(terraform_project_dir, ".terraform.lock.hcl")):
            os.remove(f)
        
        # Try initialization with plugin cache
        plugin_cache_dir = os.path.join(os.path.expanduser("~"), ".terraform.d", "plugin-cache")
        os.makedirs(plugin_cache_dir, exist_ok=True)
        os.environ["TF_PLUGIN_CACHE_DIR"] = plugin_cache_dir
        
        try:
            run_command("terraform init -reconfigure", cwd=terraform_project_dir)
        except Exception as e2:
            print_error(f"Terraform reinitialization failed: {str(e2)}")
            return project_dir, {}
    
    # Run Terraform plan
    print_info("=" * 80)
    print_info("PLANNING TERRAFORM CHANGES")
    print_info("=" * 80)
    
    # Check for any warnings in the validation log that might be important
    validation_log_path = os.path.join(terraform_project_dir, "terraform_validate_debug.log")
    if os.path.exists(validation_log_path):
        try:
            with open(validation_log_path, 'r') as log_file:
                validation_log = log_file.read()
                if "warning" in validation_log.lower():
                    print_warning("Validation completed with warnings. Check the debug log for details.")
                    print_info(f"Validation debug log: {validation_log_path}")
        except Exception as e:
            print_warning(f"Could not read validation log: {str(e)}")
    
    try:
        # Set up the plan log file for detailed output
        plan_log_file = os.path.join(project_dir, "terraform_plan.log")
        print_info(f"Logging detailed Terraform plan output to: {plan_log_file}")
        
        # Create the plan file
        plan_file = os.path.join(project_dir, "terraform.plan")
        print_info(f"Creating Terraform plan file: {plan_file}")
        
        # Command to create the plan
        plan_cmd = f"terraform plan -out={plan_file}"
        print_info(f"Running: {plan_cmd}")
        
        # Run the command and capture output
        with open(plan_log_file, 'w') as log_file:
            process = subprocess.Popen(
                plan_cmd,
                shell=True,
                cwd=terraform_project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process output in real-time
            stdout_lines = []
            for line in process.stdout:
                sys.stdout.write(line)
                stdout_lines.append(line)
                log_file.write(line)
            
            # Wait for process to complete
            process.wait()
            
            # Check for errors
            if process.returncode != 0:
                error_output = process.stderr.read()
                print_error("Terraform plan failed:")
                print_error(error_output)
                log_file.write("\nERROR OUTPUT:\n")
                log_file.write(error_output)
                
                # Analyze errors
                error_analysis = analyze_terraform_errors(error_output)
                log_file.write("\nERROR ANALYSIS:\n")
                log_file.write(json.dumps(error_analysis, indent=2))
                
                # Try to fix common issues
                if fix_terraform_issues(terraform_project_dir, error_analysis, tf_vars_file, region):
                    print_info("Attempting to re-run plan after fixing issues...")
                    log_file.write("\nRE-RUNNING PLAN AFTER FIXES:\n")
                    
                    # Re-run plan
                    try:
                        replan_cmd = f"terraform plan -out={plan_file}"
                        replan_process = subprocess.run(
                            replan_cmd,
                            shell=True,
                            cwd=terraform_project_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        
                        log_file.write(replan_process.stdout)
                        if replan_process.returncode != 0:
                            print_error("Terraform plan still failed after fixes.")
                            log_file.write("\nERROR OUTPUT AFTER FIXES:\n")
                            log_file.write(replan_process.stderr)
                            return project_dir, {}
                        else:
                            print_success("Terraform plan succeeded after fixing issues!")
                    except Exception as e:
                        print_error(f"Failed to re-run plan: {str(e)}")
                        return project_dir, {}
                else:
                    print_error("Unable to automatically fix Terraform issues.")
                    print_info("You may need to manually fix the issues in the Terraform configuration.")
                    return project_dir, {}
            
            # Create human-readable plan file
            print_info("Saving human-readable plan to: " + os.path.join(project_dir, "terraform.plan.txt"))
            try:
                show_cmd = ["terraform", "show", plan_file]
                show_output = run_command(show_cmd, cwd=terraform_project_dir, capture_output=True)
                
                with open(os.path.join(project_dir, "terraform.plan.txt"), 'w') as f:
                    f.write(show_output)
                print_success("Terraform plan saved successfully")
            except Exception as e:
                print_warning(f"Failed to save human-readable plan: {str(e)}")
    except Exception as e:
        print_error(f"Error during Terraform plan: {str(e)}")
        return project_dir, {}
    
    # Run Terraform apply
    print_info("=" * 80)
    print_info("APPLYING TERRAFORM CHANGES")
    print_info("=" * 80)
    
    # Ask for user permission before applying unless auto_approve is set
    if not args.auto_approve:
        print_info("Terraform plan has been created. Review the plan before applying.")
        print_info(f"You can find the plan at: {os.path.join(project_dir, 'terraform.plan.txt')}")
        
        user_confirm = input("Do you want to proceed with applying the Terraform plan? (y/N): ")
        if user_confirm.lower() != 'y':
            print_info("Terraform apply cancelled by user.")
            print_info(f"Your environment ID is: {env_id}")
            print_info(f"You can reuse this environment later with: buildandburn up --env-id {env_id}")
            return project_dir, {}
    
    try:
        # Set up the apply log file
        tf_apply_log = os.path.join(project_dir, "terraform_apply.log")
        print_info(f"Logging detailed Terraform apply output to: {tf_apply_log}")
        
        # Also create a separate raw output log file
        raw_output_file = os.path.join(project_dir, "terraform_apply_raw.log")
        
        # Command to apply the plan
        apply_cmd = f"terraform apply {plan_file}"
        print_info(f"Running: {apply_cmd}")
        
        with open(tf_apply_log, 'w') as log_file, open(raw_output_file, 'w') as raw_log:
            log_file.write("=" * 80 + "\n")
            log_file.write("TERRAFORM APPLY LOG\n")
            log_file.write("=" * 80 + "\n")
            log_file.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Command: {apply_cmd}\n")
            log_file.write(f"Project Directory: {terraform_project_dir}\n\n")
            
            # Run the command
            process = subprocess.Popen(
                apply_cmd,
                shell=True,
                cwd=terraform_project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process output in real-time
            resource_actions = {
                "creating": 0,
                "created": 0,
                "modifying": 0,
                "modified": 0,
                "destroying": 0,
                "destroyed": 0
            }
            
            resource_counts = {}
            
            # Monitor stdout with timeout
            start_time = time.time()
            last_activity_time = start_time
            last_progress_update = start_time
            timeout = CONFIG["TERRAFORM_APPLY_TIMEOUT"]
            
            print_info(f"Terraform apply timeout set to {timeout} seconds")
            
            # Track resources being created
            creating_resources = set()
            
            while True:
                # Check for timeout
                current_time = time.time()
                elapsed_time = current_time - start_time
                time_since_last_activity = current_time - last_activity_time
                
                # Provide periodic progress updates
                if current_time - last_progress_update > CONFIG["PROGRESS_UPDATE_INTERVAL"]:
                    print_info(f"Terraform apply in progress... ({int(elapsed_time)}s elapsed)")
                    if creating_resources:
                        print_info(f"Current resources being created: {', '.join(creating_resources)}")
                    last_progress_update = current_time
                
                # Check if process finished or timed out
                if process.poll() is not None:
                    break
                
                # Check for timeout, but only if there's been no activity for a while
                if elapsed_time > timeout:
                    should_terminate, last_activity_time = handle_terraform_timeout(
                        process, 
                        creating_resources, 
                        current_time, 
                        start_time, 
                        last_activity_time, 
                        timeout, 
                        log_file, 
                        "apply"
                    )
                    
                    if should_terminate:
                        return project_dir, {}
                    else:
                        continue
                
                # Check if output is available (non-blocking)
                line = ""
                try:
                    line = process.stdout.readline()
                except Exception as e:
                    print_warning(f"Error reading terraform output: {str(e)}")
                    time.sleep(1)
                    continue
                
                if not line:
                    # No output available, wait a bit
                    time.sleep(0.1)
                    continue
                
                # Got output, update last activity time
                last_activity_time = current_time
                
                # Write to logs
                sys.stdout.write(line)
                log_file.write(line)
                raw_log.write(line)
                
                # Parse for resource actions
                if "Creating..." in line:
                    resource_actions["creating"] += 1
                    resource_type = line.split("Creating...")[0].strip()
                    if resource_type.startswith('"') and resource_type.endswith('"'):
                        resource_type = resource_type[1:-1]
                    
                    # Add to tracking set
                    creating_resources.add(resource_type)
                    
                elif "Creation complete" in line:
                    resource_actions["created"] += 1
                    resource_type = None
                    
                    # Remove from tracking set if found
                    for rt in creating_resources.copy():
                        if rt in line:
                            creating_resources.remove(rt)
                            resource_type = rt
                            break
                    
                    # Fall back to common resource types if not found
                    if not resource_type:
                        for rt in [
                            "aws_vpc", "aws_subnet", "aws_internet_gateway", "aws_route_table",
                            "aws_security_group", "aws_eks_cluster", "aws_eks_node_group",
                            "aws_db_instance", "aws_mq_broker", "aws_iam_role"
                        ]:
                            if rt in line:
                                if rt in creating_resources:
                                    creating_resources.remove(rt)
                                resource_type = rt
                                break
                    
                    if resource_type:
                        if resource_type in resource_counts:
                            resource_counts[resource_type] += 1
                        else:
                            resource_counts[resource_type] = 1
                
                # Refresh stdout
                sys.stdout.flush()
            
            # Process has finished or timed out
            elapsed_time = time.time() - start_time
            print_info(f"Terraform process finished after {int(elapsed_time)}s")
            
            # Check for errors in stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                print_error("Terraform apply encountered errors:")
                print_error(stderr_output)
                log_file.write("\nERROR OUTPUT:\n")
                log_file.write(stderr_output)
                raw_log.write(stderr_output)
            
            # Get process exit code
            return_code = process.poll()
            
            if return_code != 0:
                print_error(f"Terraform apply failed with exit code {return_code}")
                print_error("The infrastructure may be in an inconsistent state.")
                print_warning("You should run 'buildandburn down' to clean up any partial resources.")
                
                # Check for common errors
                error_analysis = analyze_terraform_errors(stderr_output)
                log_file.write("\nERROR ANALYSIS:\n")
                log_file.write(json.dumps(error_analysis, indent=2))
                
                # Return the project directory but with empty output
                return project_dir, {}
            else:
                print_success("Terraform apply completed successfully!")
                
                # Write completed timestamp
                log_file.write(f"\nCompleted at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"Total execution time: {int(elapsed_time)} seconds\n")
                
                # Process resources first without modifying the dictionary during iteration
                processed_resources = {}
                for res_type, count in resource_counts.items():
                    res = res_type.replace("aws_", "")
                    processed_resources[res] = processed_resources.get(res, 0) + count
                
                # Now we can safely add these to resource_counts without iteration issues
                for res, count in processed_resources.items():
                    if res != res.replace("aws_", ""): # Make sure we're not adding duplicates
                        resource_counts[res] = count
                
                # Write resource summary
                log_file.write("\nRESOURCE SUMMARY:\n")
                log_file.write(f"Creating: {resource_actions['creating']}, Created: {resource_actions['created']}\n")
                log_file.write(f"Modifying: {resource_actions['modifying']}, Modified: {resource_actions['modified']}\n")
                log_file.write(f"Destroying: {resource_actions['destroying']}, Destroyed: {resource_actions['destroyed']}\n\n")
                
                log_file.write("RESOURCES CREATED:\n")
                for res_type, count in resource_counts.items():
                    log_file.write(f"- {res_type}: {count}\n")
                    print_info(f"Created {count} {res_type} resource(s)")
                
                # Write paths to logs
                print_info(f"Detailed logs available at:")
                print_info(f"- Structured log: {tf_apply_log}")
                print_info(f"- Raw output log: {raw_output_file}")
    except Exception as e:
        print_error(f"Terraform apply failed: {str(e)}")
        # Additional diagnostics
        print_info("Running diagnostic commands...")
        try:
            run_command("ls -la", cwd=terraform_project_dir)
            
            # Check for state file in multiple locations
            state_file_locations = [
                os.path.join(terraform_project_dir, "terraform.tfstate"),
                os.path.join(terraform_project_dir, "state", "terraform.tfstate")
            ]
            
            state_file_found = False
            for state_file in state_file_locations:
                if os.path.exists(state_file):
                    print_info(f"State file found at: {state_file}")
                    run_command(f"cat {state_file}", cwd=os.path.dirname(state_file))
                    state_file_found = True
                    break
            
            if not state_file_found:
                print_warning("No state file found in expected locations")
            
            run_command("env | grep TF_", cwd=terraform_project_dir)
            
            # Check for common AWS errors in the logs
            print_info("Checking for common AWS errors...")
            error_log = os.path.join(terraform_project_dir, "terraform.log")
            if os.path.exists(error_log):
                with open(error_log, 'r') as f:
                    log_content = f.read()
                    if "AccessDenied" in log_content:
                        print_error("AWS Access Denied error detected. Check your IAM permissions.")
                    if "RequestTimeTooSkewed" in log_content:
                        print_error("AWS time synchronization issue detected. Check your system clock.")
            else:
                print_warning("No terraform.log file found for detailed error analysis.")
        except Exception as diag_error:
            print_warning(f"Diagnostic command failed: {str(diag_error)}")
        
        # Return with empty output instead of exiting
        return project_dir, {}
    
    # Get Terraform outputs
    print_info("Retrieving Terraform outputs...")
    try:
        # Use capture_output=True to get the command output as text
        result = run_command(["terraform", "output", "-json"], cwd=terraform_project_dir, capture_output=True)
        
        # Check if we got a string (command output) or something else
        if hasattr(result, 'stdout'):
            tf_output = json.loads(result.stdout)
        else:
            # We got an integer return code or other non-output value
            print_error("Failed to capture Terraform output")
            tf_output = {}
    except Exception as e:
        print_error(f"Failed to get Terraform outputs: {str(e)}")
        print_warning("Continuing with empty output map")
        tf_output = {}
    
    # Get and print access information
    kubeconfig_path = os.path.join(project_dir, "kubeconfig")
    namespace = f"bb-{manifest['name']}"
    access_info = get_access_info(kubeconfig_path, namespace, tf_output)
    
    # Save environment information
    env_info = {
        "env_id": env_id,
        "project_name": manifest['name'],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": manifest,
        "terraform_output": tf_output,
        "region": region,
        "resources": resources,
        "estimated_cost_per_hour": cost_per_hour,
        "state_file": os.path.join(state_dir, "terraform.tfstate"),
        "terraform_dir": terraform_project_dir,
        "variables_file": tf_vars_file,
        "plan_file": os.path.join(project_dir, "terraform.plan"),
        "working_dir": project_dir,
        "access_info": access_info  # Add access info to env_info
    }
    
    env_info_file = os.path.join(project_dir, "env_info.json")
    print_info(f"Saving environment information to: {env_info_file}")
    with open(env_info_file, 'w') as f:
        json.dump(env_info, f, indent=2)
    
    print_success("Infrastructure provisioning completed successfully!")
    return project_dir, tf_output

def prepare_kubernetes_values(manifest, tf_output, k8s_dir, project_dir):
    """Prepare Kubernetes values file from manifest and Terraform outputs."""
    values = {}
    
    # Copy main attributes from manifest
    if 'name' in manifest:
        values['name'] = manifest['name']
    
    if 'description' in manifest:
        values['description'] = manifest['description']
    
    # Process ingress configuration
    if 'ingress' in manifest:
        values['ingress'] = manifest['ingress']
    
    # Process services
    if 'services' in manifest:
        values['services'] = []
        for service in manifest['services']:
            service_values = dict(service)
            
            # Update with terraform outputs if available
            # For example, add database connection strings, etc.
            if 'database_endpoint' in tf_output and 'database' in service.get('dependencies', []):
                if 'env' not in service_values:
                    service_values['env'] = []
                
                service_values['env'].append({
                    "name": "DATABASE_URL",
                    "value": tf_output['database_endpoint']['value']
                })
                service_values['env'].append({
                    "name": "DATABASE_USER",
                    "value": tf_output['database_username']['value']
                })
                service_values['env'].append({
                    "name": "DATABASE_PASSWORD",
                    "value": tf_output['database_password']['value']
                })
            
            if 'mq_endpoint' in tf_output and 'mq' in service.get('dependencies', []):
                if 'env' not in service_values:
                    service_values['env'] = []
                
                service_values['env'].append({
                    "name": "MQ_URL",
                    "value": tf_output['mq_endpoint']['value']
                })
                service_values['env'].append({
                    "name": "MQ_USER",
                    "value": tf_output['mq_username']['value']
                })
                service_values['env'].append({
                    "name": "MQ_PASSWORD",
                    "value": tf_output['mq_password']['value']
                })
            
            # Add Redis connection info if service has Redis dependency
            if 'redis_primary_endpoint' in tf_output and 'redis' in service.get('dependencies', []):
                if 'env' not in service_values:
                    service_values['env'] = []
                
                service_values['env'].append({
                    "name": "REDIS_HOST",
                    "value": tf_output['redis_primary_endpoint']['value']
                })
                
                if 'redis_port' in tf_output and tf_output['redis_port']['value']:
                    service_values['env'].append({
                        "name": "REDIS_PORT",
                        "value": str(tf_output['redis_port']['value'])
                    })
                else:
                    service_values['env'].append({
                        "name": "REDIS_PORT",
                        "value": "6379"  # Default Redis port
                    })
                
                # Add reader endpoint if available
                if 'redis_reader_endpoint' in tf_output and tf_output['redis_reader_endpoint']['value']:
                    service_values['env'].append({
                        "name": "REDIS_READER_HOST",
                        "value": tf_output['redis_reader_endpoint']['value']
                    })
                
                # Add connection URL format for convenience
                redis_url = f"redis://{tf_output['redis_primary_endpoint']['value']}:{tf_output.get('redis_port', {}).get('value', 6379)}"
                service_values['env'].append({
                    "name": "REDIS_URL",
                    "value": redis_url
                })
            
            values['services'].append(service_values)
    
    # Write values to file
    values_file = os.path.join(project_dir, "values.yaml")
    print_info(f"Writing Kubernetes values to: {values_file}")
    
    with open(values_file, 'w') as f:
        yaml.dump(values, f)
    
    return values_file

def deploy_to_kubernetes(manifest, tf_output, k8s_dir, project_dir):
    """Deploy services to Kubernetes."""
    print_info("=" * 80)
    print_info("DEPLOYING TO KUBERNETES")
    print_info("=" * 80)
    
    # Get kubeconfig
    print_info("Retrieving kubeconfig from Terraform outputs...")
    if 'kubeconfig' not in tf_output or 'value' not in tf_output['kubeconfig']:
        print_error("Kubeconfig not found in Terraform outputs")
        return False
        
    kubeconfig = tf_output['kubeconfig']['value']
    kubeconfig_path = os.path.join(project_dir, "kubeconfig")
    print_info(f"Saving kubeconfig to: {kubeconfig_path}")
    with open(kubeconfig_path, 'w') as f:
        f.write(kubeconfig)
    
    # Prepare Kubernetes values
    print_info("Preparing Kubernetes values...")
    try:
        values_file = prepare_kubernetes_values(manifest, tf_output, k8s_dir, project_dir)
    except Exception as e:
        print_error(f"Failed to prepare Kubernetes values: {str(e)}")
        return False
    
    # Create Kubernetes namespace
    namespace = f"bb-{manifest['name']}"
    print_info(f"Creating Kubernetes namespace: {namespace}")
    
    # Set up the deployment log file
    deploy_log_file = os.path.join(project_dir, "kubernetes_deploy.log")
    print_info(f"Logging detailed deployment output to: {deploy_log_file}")
    
    try:
        with open(deploy_log_file, 'w') as log_file:
            # Set up KUBECONFIG environment variable for all subsequent commands
            env = os.environ.copy()
            env['KUBECONFIG'] = kubeconfig_path
            
            # Check if kubectl is installed
            print_info("Verifying kubectl is installed...")
            if not is_kubectl_installed():
                print_error("kubectl command not found. Please make sure kubectl is installed and available in your PATH.")
                return False
            
            # Create namespace using run_command with proper environment
            print_info(f"Creating namespace: {namespace}")
            ns_cmd = ["kubectl", "create", "namespace", namespace, "--dry-run=client", "-o", "yaml"]
            apply_cmd = ["kubectl", "apply", "-f", "-"]
            
            # Execute as a pipeline using subprocess
            log_file.write(f"Creating namespace with command: {' '.join(ns_cmd)} | {' '.join(apply_cmd)}\n")
            ns_process = subprocess.Popen(
                ns_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            apply_process = subprocess.Popen(
                apply_cmd,
                stdin=ns_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Close ns_process's stdout to allow apply_process to receive EOF
            ns_process.stdout.close()
            apply_output, apply_error = apply_process.communicate()
            
            if apply_process.returncode != 0 and "already exists" not in apply_error.decode():
                print_error(f"Failed to create namespace: {apply_error.decode()}")
                log_file.write(f"Failed to create namespace: {apply_error.decode()}\n")
                # Continue despite error, as the namespace might still work for deployment
            else:
                print_success("Namespace created/verified successfully.")
                log_file.write("Namespace created/verified successfully.\n")
            
            # Deploy services using appropriate method
            print_info("Deploying Kubernetes resources...")
            log_file.write("Deploying Kubernetes resources...\n")
            
            # Determine deployment method based on available resources and manifest settings
            helm_chart_path = None
            k8s_manifests_path = None
            
            # First, check if manifest explicitly defines a k8s_path
            if 'k8s_path' in manifest:
                custom_k8s_path = os.path.abspath(manifest['k8s_path'])
                if os.path.exists(custom_k8s_path):
                    print_info(f"Using custom Kubernetes path from manifest: {custom_k8s_path}")
                    
                    # Check if it's a Helm chart or k8s manifests
                    if os.path.exists(os.path.join(custom_k8s_path, "Chart.yaml")):
                        helm_chart_path = custom_k8s_path
                    else:
                        k8s_manifests_path = custom_k8s_path
                else:
                    print_warning(f"Custom k8s_path specified in manifest does not exist: {custom_k8s_path}")
            
            # If no custom path specified, check standard locations
            if not helm_chart_path and not k8s_manifests_path:
                # Check for Helm chart in standard location
                if os.path.exists(os.path.join(k8s_dir, "chart", "Chart.yaml")):
                    helm_chart_path = os.path.join(k8s_dir, "chart")
                    print_info(f"Found Helm chart at standard location: {helm_chart_path}")
                
                # Check for k8s manifests directory
                elif os.path.exists(os.path.join(k8s_dir, "manifests")):
                    k8s_manifests_path = os.path.join(k8s_dir, "manifests")
                    print_info(f"Found Kubernetes manifests at standard location: {k8s_manifests_path}")
                
                # Check for individual manifest files in k8s dir
                elif os.path.exists(k8s_dir):
                    yaml_files = [f for f in os.listdir(k8s_dir) if f.endswith(('.yaml', '.yml'))]
                    if yaml_files:
                        k8s_manifests_path = k8s_dir
                        print_info(f"Found Kubernetes manifest files in k8s directory: {k8s_manifests_path}")
            
            deployed = False
            
            # Check if Helm is installed (only if we need it)
            helm_installed = False
            if helm_chart_path:
                helm_check_cmd = ["helm", "version"]
                print_info("Checking for Helm installation...")
                helm_check = subprocess.run(
                    helm_check_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    env=env
                )
                if helm_check.returncode == 0:
                    helm_installed = True
                    print_info("Helm detected, will use for chart-based deployments.")
                    log_file.write("Helm detected, will use for chart-based deployments.\n")
                else:
                    print_warning("Helm chart found but Helm is not installed. Will fall back to generated manifests.")
                    log_file.write("Helm chart found but Helm is not installed. Falling back to generated manifests.\n")
            
            # Deploy using Helm if chart exists and Helm is installed
            if helm_chart_path and helm_installed:
                print_info(f"Deploying using Helm chart at: {helm_chart_path}")
                log_file.write(f"Deploying using Helm chart at: {helm_chart_path}\n")
                
                # Use Helm for deployment
                helm_cmd = [
                    "helm", "upgrade", "--install", 
                    manifest['name'], helm_chart_path, 
                    "--values", values_file, 
                    "--namespace", namespace,
                    "--create-namespace"  # Allow Helm to create the namespace
                ]
                
                print_info(f"Running Helm command: {' '.join(helm_cmd)}")
                log_file.write(f"Helm command: {' '.join(helm_cmd)}\n")
                
                helm_process = subprocess.run(
                    helm_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )
                
                log_file.write(f"Helm output: {helm_process.stdout}\n")
                print_info(helm_process.stdout)
                
                if helm_process.returncode != 0:
                    print_warning("Helm deployment encountered issues:")
                    print_warning(helm_process.stderr)
                    log_file.write(f"Helm errors: {helm_process.stderr}\n")
                    
                    # Try cleaning up namespace and redeploying if there's an ownership issue
                    if "invalid ownership metadata" in helm_process.stderr:
                        print_info("Detected namespace ownership issue. Cleaning up namespace...")
                        log_file.write("Detected namespace ownership issue. Cleaning up namespace...\n")
                        
                        # Delete the namespace
                        delete_cmd = ["kubectl", "delete", "namespace", namespace]
                        print_info(f"Running: {' '.join(delete_cmd)}")
                        log_file.write(f"Kubectl command: {' '.join(delete_cmd)}\n")
                        
                        delete_process = subprocess.run(
                            delete_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            env=env
                        )
                        
                        if delete_process.returncode == 0:
                            print_info("Namespace deleted successfully. Retrying deployment...")
                            log_file.write("Namespace deleted successfully. Retrying deployment...\n")
                            
                            # Retry the Helm deployment
                            helm_process = subprocess.run(
                                helm_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env
                            )
                            
                            log_file.write(f"Helm retry output: {helm_process.stdout}\n")
                            print_info(helm_process.stdout)
                            
                            if helm_process.returncode == 0:
                                print_success("Helm deployment successful on retry!")
                                log_file.write("Helm deployment successful on retry!\n")
                                deployed = True
                            else:
                                print_warning("Helm deployment still failing after namespace cleanup:")
                                print_warning(helm_process.stderr)
                                log_file.write(f"Helm retry errors: {helm_process.stderr}\n")
                        else:
                            print_warning(f"Failed to delete namespace: {delete_process.stderr}")
                            log_file.write(f"Failed to delete namespace: {delete_process.stderr}\n")
                    
                    # If Helm still failed but we have manifest files, try those as fallback
                    if not deployed and k8s_manifests_path:
                        print_info("Falling back to Kubernetes manifests after Helm failure")
                        log_file.write("Falling back to Kubernetes manifests after Helm failure\n")
                    elif not deployed:
                        print_error("Helm deployment failed and no fallback manifests available.")
                        log_file.write("Helm deployment failed and no fallback manifests available.\n")
                        return False
                else:
                    print_success("Helm deployment successful!")
                    log_file.write("Helm deployment successful!\n")
                    deployed = True
            
            # Deploy using kubectl apply with manifest files if they exist and Helm didn't succeed
            if not deployed and k8s_manifests_path:
                print_info(f"Deploying using Kubernetes manifests at: {k8s_manifests_path}")
                log_file.write(f"Deploying using Kubernetes manifests at: {k8s_manifests_path}\n")
                
                # Determine if it's a directory with manifests or a single file
                if os.path.isdir(k8s_manifests_path):
                    # Check if there are YAML files in the directory
                    yaml_files = [f for f in os.listdir(k8s_manifests_path) if f.endswith(('.yaml', '.yml'))]
                    
                    if yaml_files:
                        # Apply all YAML files in the directory
                        print_info(f"Found {len(yaml_files)} YAML files in {k8s_manifests_path}")
                        log_file.write(f"Found {len(yaml_files)} YAML files in {k8s_manifests_path}\n")
                        
                        # Apply each file with values substituted from values file
                        for yaml_file in yaml_files:
                            file_path = os.path.join(k8s_manifests_path, yaml_file)
                            print_info(f"Applying manifest: {yaml_file}")
                            log_file.write(f"Applying manifest: {yaml_file}\n")
                            
                            # Apply the manifest file
                            apply_cmd = ["kubectl", "apply", "-f", file_path, "--namespace", namespace]
                            print_info(f"Running: {' '.join(apply_cmd)}")
                            log_file.write(f"Kubectl command: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.run(
                                apply_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env
                            )
                            
                            log_file.write(f"Kubectl output: {apply_process.stdout}\n")
                            print_info(apply_process.stdout)
                            
                            if apply_process.returncode != 0:
                                print_warning(f"Warning applying {yaml_file}: {apply_process.stderr}")
                                log_file.write(f"Warning applying {yaml_file}: {apply_process.stderr}\n")
                            
                        deployed = True
                    else:
                        print_warning(f"No YAML files found in {k8s_manifests_path}")
                        log_file.write(f"No YAML files found in {k8s_manifests_path}\n")
                else:
                    # Apply the single manifest file
                    apply_cmd = ["kubectl", "apply", "-f", k8s_manifests_path, "--namespace", namespace]
                    print_info(f"Running: {' '.join(apply_cmd)}")
                    log_file.write(f"Kubectl command: {' '.join(apply_cmd)}\n")
                    
                    apply_process = subprocess.run(
                        apply_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env
                    )
                    
                    log_file.write(f"Kubectl output: {apply_process.stdout}\n")
                    print_info(apply_process.stdout)
                    
                    if apply_process.returncode != 0:
                        print_warning(f"Warning applying manifest: {apply_process.stderr}")
                        log_file.write(f"Warning applying manifest: {apply_process.stderr}\n")
                    else:
                        deployed = True
            
            # If no manifests or helm chart found, generate Kubernetes resources from the values file
            if not deployed:
                print_info("No pre-defined Kubernetes resources found. Generating from manifest...")
                log_file.write("No pre-defined Kubernetes resources found. Generating from manifest...\n")
                
                # Generate Kubernetes YAML from values
                k8s_yaml_file = os.path.join(project_dir, "kubernetes.yaml")
                try:
                    with open(values_file, 'r') as f:
                        values = yaml.safe_load(f)
                    
                    # Generate Kubernetes resources
                    resources = []
                    
                    # Add namespace
                    resources.append({
                        "apiVersion": "v1",
                        "kind": "Namespace",
                        "metadata": {
                            "name": namespace
                        }
                    })
                    
                    # First, collect all service definitions to map dependencies
                    service_map = {}
                    for service in values.get('services', []):
                        service_map[service['name']] = service
                    
                    # Look for dependencies between services
                    for service_name, service_data in service_map.items():
                        if 'dependencies' in service_data:
                            print_info(f"Service {service_name} has dependencies: {service_data['dependencies']}")
                            log_file.write(f"Service {service_name} has dependencies: {service_data['dependencies']}\n")
                    
                    # Add services
                    for service in values.get('services', []):
                        # Deployment
                        deployment = {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "metadata": {
                                "name": service['name'],
                                "namespace": namespace
                            },
                            "spec": {
                                "replicas": service.get('replicas', 1),
                                "selector": {
                                    "matchLabels": {
                                        "app": service['name']
                                    }
                                },
                                "template": {
                                    "metadata": {
                                        "labels": {
                                            "app": service['name']
                                        }
                                    },
                                    "spec": {
                                        "containers": [{
                                            "name": service['name'],
                                            "image": service['image'],
                                            "ports": service.get('ports', []),
                                            "env": service.get('env', [])
                                        }]
                                    }
                                }
                            }
                        }
                        
                        # Add environment variables for service dependencies
                        if 'dependencies' in service:
                            for dep in service['dependencies']:
                                if dep in service_map:
                                    # Add env vars for dependency connection
                                    dep_env_vars = [
                                        {"name": f"{dep.upper()}_SERVICE_HOST", "value": f"{dep}.{namespace}.svc.cluster.local"},
                                        {"name": f"{dep.upper()}_SERVICE_PORT", "value": "80"}  # Default port
                                    ]
                                    
                                    # Ensure env list exists
                                    if "env" not in deployment["spec"]["template"]["spec"]["containers"][0]:
                                        deployment["spec"]["template"]["spec"]["containers"][0]["env"] = []
                                    
                                    deployment["spec"]["template"]["spec"]["containers"][0]["env"].extend(dep_env_vars)
                        
                        resources.append(deployment)
                        
                        # Service
                        svc = {
                            "apiVersion": "v1",
                            "kind": "Service",
                            "metadata": {
                                "name": service['name'],
                                "namespace": namespace
                            },
                            "spec": {
                                "type": service.get('service', {}).get('type', 'ClusterIP'),
                                "selector": {
                                    "app": service['name']
                                },
                                "ports": service.get('service', {}).get('ports', [
                                    {"port": 80, "targetPort": 8080, "protocol": "TCP"}
                                ])
                            }
                        }
                        resources.append(svc)
                        
                        # Ingress
                        if service.get('ingress', {}).get('enabled', False):
                            ingress = {
                                "apiVersion": "networking.k8s.io/v1",
                                "kind": "Ingress",
                                "metadata": {
                                    "name": service['name'],
                                    "namespace": namespace,
                                    "annotations": {
                                        "kubernetes.io/ingress.class": service.get('ingress', {}).get('className', 'nginx')
                                    }
                                },
                                "spec": {
                                    "rules": [{
                                        "host": service.get('ingress', {}).get('host', f"{service['name']}.{values.get('ingress', {}).get('domain', 'example.com')}"),
                                        "http": {
                                            "paths": [{
                                                "path": service.get('ingress', {}).get('path', '/'),
                                                "pathType": service.get('ingress', {}).get('pathType', 'Prefix'),
                                                "backend": {
                                                    "service": {
                                                        "name": service['name'],
                                                        "port": {
                                                            "number": 80
                                                        }
                                                    }
                                                }
                                            }]
                                        }
                                    }]
                                }
                            }
                            resources.append(ingress)
                    
                    # Write full YAML to file
                    with open(k8s_yaml_file, 'w') as f:
                        yaml.dump_all(resources, f)
                    
                    # Apply YAML with kubectl
                    kubectl_cmd = ["kubectl", "apply", "-f", k8s_yaml_file]
                    print_info(f"Running: {' '.join(kubectl_cmd)}")
                    log_file.write(f"Kubectl command: {' '.join(kubectl_cmd)}\n")
                    
                    kubectl_process = subprocess.run(
                        kubectl_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env
                    )
                    
                    log_file.write(f"Kubectl output: {kubectl_process.stdout}\n")
                    print_info(kubectl_process.stdout)
                    
                    if kubectl_process.returncode != 0:
                        print_error("Kubectl deployment failed:")
                        print_error(kubectl_process.stderr)
                        log_file.write(f"Kubectl errors: {kubectl_process.stderr}\n")
                        log_file.write("Kubectl deployment failed.\n")
                        return False
                    else:
                        print_success("Kubectl deployment successful!")
                        log_file.write("Kubectl deployment successful!\n")
                        deployed = True
                except Exception as e:
                    print_error(f"Failed to generate Kubernetes YAML: {str(e)}")
                    log_file.write(f"Failed to generate Kubernetes YAML: {str(e)}\n")
                    return False
            
            if not deployed:
                print_error("All deployment methods failed.")
                log_file.write("All deployment methods failed.\n")
                return False
            
            # Wait for pods to be ready
            print_info("Waiting for pods to be ready...")
            log_file.write("Waiting for pods to be ready...\n")
            
            # Wait up to 5 minutes for pods to be ready
            wait_cmd = ["kubectl", "wait", "--for=condition=ready", "pod", "--all", "-n", namespace, "--timeout=300s"]
            print_info(f"Running: {' '.join(wait_cmd)}")
            log_file.write(f"Wait command: {' '.join(wait_cmd)}\n")
            
            wait_process = subprocess.run(
                wait_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            if wait_process.returncode != 0:
                print_warning("Not all pods are ready yet, but continuing...")
                print_warning(wait_process.stderr)
                log_file.write(f"Pod wait warning: {wait_process.stderr}\n")
            else:
                print_success("All pods are ready!")
                log_file.write("All pods are ready!\n")
            
            # Verify deployment
            print_info("Verifying deployment...")
            log_file.write("Verifying deployment...\n")
            
            # Get pods
            pods_cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "wide"]
            print_info(f"Running: {' '.join(pods_cmd)}")
            log_file.write(f"Pods command: {' '.join(pods_cmd)}\n")
            
            pods_process = subprocess.run(
                pods_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            log_file.write(f"Pods output: {pods_process.stdout}\n")
            print_info(f"Deployed pods:\n{pods_process.stdout}")
            
            # Get services
            services_cmd = ["kubectl", "get", "svc", "-n", namespace, "-o", "wide"]
            print_info(f"Running: {' '.join(services_cmd)}")
            log_file.write(f"Services command: {' '.join(services_cmd)}\n")
            
            services_process = subprocess.run(
                services_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            log_file.write(f"Services output: {services_process.stdout}\n")
            print_info(f"Deployed services:\n{services_process.stdout}")
            
            # Get ingresses
            ingress_cmd = ["kubectl", "get", "ingress", "-n", namespace, "-o", "wide"]
            print_info(f"Running: {' '.join(ingress_cmd)}")
            log_file.write(f"Ingress command: {' '.join(ingress_cmd)}\n")
            
            ingress_process = subprocess.run(
                ingress_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            if ingress_process.returncode == 0 and ingress_process.stdout.strip():
                log_file.write(f"Ingress output: {ingress_process.stdout}\n")
                print_info(f"Deployed ingresses:\n{ingress_process.stdout}")
            else:
                print_info("No ingresses deployed or found.")
                log_file.write("No ingresses deployed or found.\n")
            
            print_success("Kubernetes deployment completed successfully!")
            log_file.write("Kubernetes deployment completed successfully!\n")
            return True
    except Exception as e:
        print_error(f"Failed to deploy to Kubernetes: {str(e)}")
        traceback.print_exc()
        return False

def get_access_info(kubeconfig_path, namespace, tf_output):
    """Get access information for the deployed services."""
    access_info = {
        "services": {},
        "ingresses": {},
        "database": {},
        "message_queue": {},
        "redis": {}
    }
    
    try:
        # Set the KUBECONFIG environment variable
        env = os.environ.copy()
        env["KUBECONFIG"] = kubeconfig_path
        
        # Get service endpoints using list format
        services_result = run_command(
            ["kubectl", "get", "svc", "-n", namespace, "-o", "json"], 
            capture_output=True,
            env=env
        )
        
        if hasattr(services_result, 'stdout'):
            services = json.loads(services_result.stdout)
            
            # Service endpoints
            for svc in services.get("items", []):
                svc_name = svc["metadata"]["name"]
                svc_type = svc["spec"]["type"]
                
                if svc_type == "LoadBalancer":
                    if "status" in svc and "loadBalancer" in svc["status"] and "ingress" in svc["status"]["loadBalancer"]:
                        lb = svc["status"]["loadBalancer"]["ingress"][0]
                        if "hostname" in lb:
                            access_info["services"][svc_name] = f"http://{lb['hostname']}"
                        elif "ip" in lb:
                            access_info["services"][svc_name] = f"http://{lb['ip']}"
                    else:
                        access_info["services"][svc_name] = f"LoadBalancer pending for {svc_name}"
                else:
                    access_info["services"][svc_name] = f"Service: {svc_name}.{namespace}.svc.cluster.local"
        
        # Get ingress endpoints using list format
        ingress_result = run_command(
            ["kubectl", "get", "ingress", "-n", namespace, "-o", "json"], 
            capture_output=True, 
            allow_fail=True,
            env=env
        )
        
        if hasattr(ingress_result, 'stdout') and ingress_result.returncode == 0:
            try:
                ingresses = json.loads(ingress_result.stdout)
                
                # Ingress endpoints
                for ing in ingresses.get("items", []):
                    ing_name = ing["metadata"]["name"]
                    
                    if "status" in ing and "loadBalancer" in ing["status"] and "ingress" in ing["status"]["loadBalancer"]:
                        ing_hosts = []
                        
                        # Get all hosts defined in the ingress
                        if "rules" in ing["spec"]:
                            for rule in ing["spec"]["rules"]:
                                if "host" in rule:
                                    ing_hosts.append(rule["host"])
                        
                        # Get the load balancer address
                        lb_addresses = []
                        for lb in ing["status"]["loadBalancer"]["ingress"]:
                            if "hostname" in lb:
                                lb_addresses.append(lb["hostname"])
                            elif "ip" in lb:
                                lb_addresses.append(lb["ip"])
                        
                        if ing_hosts and lb_addresses:
                            # Combine hosts with load balancer for URLs
                            for host in ing_hosts:
                                if host:
                                    access_info["ingresses"][ing_name] = f"http://{host}"
                                else:
                                    access_info["ingresses"][ing_name] = f"http://{lb_addresses[0]}"
                        elif lb_addresses:
                            access_info["ingresses"][ing_name] = f"http://{lb_addresses[0]}"
                        else:
                            access_info["ingresses"][ing_name] = f"Ingress address pending for {ing_name}"
            except json.JSONDecodeError:
                print_warning("Failed to parse ingress information as JSON")
    except Exception as e:
        print_warning(f"Failed to get complete service access information: {str(e)}")
    
    # Database connection info
    if 'database_endpoint' in tf_output and tf_output['database_endpoint']['value']:
        access_info["database"] = {
            "endpoint": tf_output['database_endpoint']['value'],
            "username": tf_output['database_username']['value'],
            "password": "(hidden for security)"
        }
    
    # Message queue connection info
    if 'mq_endpoint' in tf_output and tf_output['mq_endpoint']['value']:
        access_info["message_queue"] = {
            "endpoint": tf_output['mq_endpoint']['value'],
            "username": tf_output['mq_username']['value'],
            "password": "(hidden for security)"
        }
    
    # Redis connection info
    if 'redis_primary_endpoint' in tf_output and tf_output['redis_primary_endpoint']['value']:
        access_info["redis"] = {
            "primary_endpoint": tf_output['redis_primary_endpoint']['value'],
            "reader_endpoint": tf_output.get('redis_reader_endpoint', {}).get('value', ""),
            "port": tf_output.get('redis_port', {}).get('value', 6379),
            "connection_url": "(hidden for security)"
        }
    
    # Add a 'primary_url' field that identifies the main application URL
    # Determine the primary URL from ingresses or services
    if access_info["ingresses"]:
        # Prefer the first ingress
        primary_ingress = list(access_info["ingresses"].keys())[0]
        access_info["primary_url"] = access_info["ingresses"][primary_ingress]
    elif access_info["services"]:
        # If no ingresses, use the first LoadBalancer service
        for svc_name, svc_url in access_info["services"].items():
            if svc_url.startswith("http://"):
                access_info["primary_url"] = svc_url
                break
    
    return access_info

def analyze_terraform_errors(error_output):
    """Analyze Terraform error output to provide helpful suggestions."""
    errors = []
    suggestions = []
    
    common_error_patterns = {
        "provider configuration not present": {
            "diagnosis": "Provider configuration is missing or invalid",
            "suggestion": "Check the provider blocks in your Terraform files. Add a proper providers.tf file.",
            "auto_fixable": True,
            "fix_action": "add_provider_config"
        },
        "registry.terraform.io": {
            "diagnosis": "Provider registry issue or connectivity problem",
            "suggestion": "Try running terraform init -upgrade to refresh provider cache, or check internet connectivity",
            "auto_fixable": True,
            "fix_action": "reinit_upgrade"
        },
        "No value for required variable": {
            "diagnosis": "Missing required Terraform variable value",
            "suggestion": "Ensure all required variables are set in your tfvars file",
            "auto_fixable": True,
            "fix_action": "check_required_vars"
        },
        "provider configuration block for provider": {
            "diagnosis": "Duplicate provider configuration block",
            "suggestion": "Remove duplicate provider blocks from your Terraform files",
            "auto_fixable": True,
            "fix_action": "fix_duplicate_providers"
        },
        "Cannot process schema for this provider": {
            "diagnosis": "Plugin cache may be corrupted",
            "suggestion": "Try clearing the .terraform directory and reinitializing",
            "auto_fixable": True, 
            "fix_action": "clear_plugin_cache"
        },
        "Error: error configuring Terraform AWS Provider": {
            "diagnosis": "AWS provider configuration issue",
            "suggestion": "Check AWS credentials and region configuration",
            "auto_fixable": False
        },
        "Error: error validating provider credentials": {
            "diagnosis": "AWS credentials are invalid or missing",
            "suggestion": "Verify AWS credentials are properly configured",
            "auto_fixable": False
        },
        "Invalid block": {
            "diagnosis": "Syntax error in Terraform configuration",
            "suggestion": "Check for syntax errors like missing brackets or quotes in your Terraform files",
            "auto_fixable": True,
            "fix_action": "auto_format"
        },
        "Unsupported argument": {
            "diagnosis": "Using an argument that is not supported by the resource/provider",
            "suggestion": "Remove or fix the unsupported argument in your Terraform configuration",
            "auto_fixable": False
        }
    }
    
    error_details = None
    auto_fix_possible = False
    fix_actions = []
    
    for line in error_output:
        for pattern, info in common_error_patterns.items():
            if pattern in line:
                diagnosis = info["diagnosis"]
                suggestion = info["suggestion"]
                
                if diagnosis not in errors:
                    errors.append(diagnosis)
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
                
                if info.get("auto_fixable", False):
                    auto_fix_possible = True
                    if info["fix_action"] not in fix_actions:
                        fix_actions.append(info["fix_action"])
                
                # Store specific error details for fixing
                if error_details is None and "auto_fixable" in info and info["auto_fixable"]:
                    error_details = {
                        "pattern": pattern,
                        "line": line,
                        "fix_action": info["fix_action"]
                    }
    
    return {
        "errors": errors,
        "suggestions": suggestions,
        "auto_fix_possible": auto_fix_possible,
        "fix_actions": fix_actions,
        "error_details": error_details
    }

def cmd_up(args):
    """Create a new build-and-burn environment."""
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENT CREATION")
    print_info("=" * 80)
    
    # Generate or use provided environment ID
    env_id = args.env_id or generate_env_id()
    print_info(f"Using environment ID: {env_id}")
    
    # Load manifest
    print_info(f"Loading manifest file: {args.manifest}")
    try:
        manifest = load_manifest(args.manifest)
        print_info("Manifest loaded successfully:")
        print(yaml.dump(manifest, default_flow_style=False))
    except Exception as e:
        print_error(f"Failed to load manifest file: {str(e)}")
        return False
    
    # Get project directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    terraform_dir = os.path.join(project_root, "terraform")
    k8s_dir = os.path.join(project_root, "k8s")
    
    print_info(f"Current directory: {current_dir}")
    print_info(f"Project root: {project_root}")
    print_info(f"Terraform directory: {terraform_dir}")
    print_info(f"Kubernetes directory: {k8s_dir}")
    
    # Enable debug logging
    os.environ['BUILDANDBURN_DEBUG'] = '1'
    
    # Check if this is a dry run
    if hasattr(args, 'dry_run') and args.dry_run:
        print_info("=" * 80)
        print_info("DRY RUN MODE - Validating configuration only")
        print_info("=" * 80)
        
        # Validate terraform configuration
        terraform_project_dir = os.path.join(terraform_dir)
        if not os.path.exists(terraform_project_dir):
            print_error(f"Terraform project directory not found: {terraform_project_dir}")
            return False
        
        # Run preflight checks
        preflight_success = run_preflight_checks(manifest, env_id, terraform_project_dir)
        if not preflight_success:
            print_error("Preflight checks failed.")
            return False
            
        # Check Kubernetes resources
        try:
            # Determine whether to auto-generate Kubernetes resources
            auto_generate = not args.no_generate_k8s if hasattr(args, 'no_generate_k8s') else True
            
            # Check if Kubernetes resources are available
            k8s_resources_path = ensure_k8s_resources(manifest, k8s_dir, os.getcwd(), auto_generate=False)
            if k8s_resources_path:
                print_success(f"Kubernetes resources found at: {k8s_resources_path}")
            elif auto_generate:
                print_info("Kubernetes resources will be generated during deployment")
            else:
                print_warning("No Kubernetes resources found and auto-generation is disabled")
                
            print_info("=" * 80)
            print_success("DRY RUN VALIDATION SUCCESSFUL - Configuration looks good")
            print_info("=" * 80)
            return True
        except Exception as e:
            print_error(f"Kubernetes resources validation failed: {str(e)}")
            return False
    
    # Provision infrastructure - pass the skip_module_confirmation flag
    project_dir, tf_output = provision_infrastructure(manifest, env_id, terraform_dir, args=args)
    
    # Check if infrastructure provisioning was successful
    if not project_dir or not tf_output:
        print_error("Infrastructure provisioning failed.")
        return False
    
    try:
        # Determine whether to auto-generate Kubernetes resources
        auto_generate = not args.no_generate_k8s if hasattr(args, 'no_generate_k8s') else True
        
        # Ensure Kubernetes resources are available, generate if needed and if auto_generate is enabled
        k8s_dir = ensure_k8s_resources(manifest, k8s_dir, project_dir, auto_generate)
        print_info(f"Using Kubernetes resources from: {k8s_dir}")
        
        # Deploy to Kubernetes
        deploy_success = deploy_to_kubernetes(manifest, tf_output, k8s_dir, project_dir)
        if not deploy_success:
            print_error("Kubernetes deployment failed.")
            print_warning("The infrastructure has been provisioned, but application deployment failed.")
            print_info(f"You can retry the deployment or destroy the infrastructure with: buildandburn down {env_id}")
            return False
    
        # Get and print access information
        kubeconfig_path = os.path.join(project_dir, "kubeconfig")
        namespace = f"bb-{manifest['name']}"
        access_info = get_access_info(kubeconfig_path, namespace, tf_output)
        
        print_info("=" * 80)
        print_success(f"ENVIRONMENT CREATED SUCCESSFULLY")
        print_info("=" * 80)
        print_success(f"Environment ID: {env_id}")
        print_info("Access Information:")
        print(json.dumps(access_info, indent=2))
        
        # Prominently display the primary URL if available
        if "primary_url" in access_info:
            print_info("=" * 80)
            print_success(f"APPLICATION URL: {access_info['primary_url']}")
            print_info("=" * 80)
        elif access_info["ingresses"]:
            # Show the first ingress URL
            first_ingress = list(access_info["ingresses"].keys())[0]
            print_info("=" * 80)
            print_success(f"APPLICATION URL: {access_info['ingresses'][first_ingress]}")
            print_info("=" * 80)
        elif any(url.startswith("http://") for url in access_info["services"].values()):
            # Find the first service with an HTTP URL
            for svc_name, url in access_info["services"].items():
                if url.startswith("http://"):
                    print_info("=" * 80)
                    print_success(f"APPLICATION URL: {url}")
                    print_info("=" * 80)
                    break
        
        print_info(f"\nTo destroy this environment, run: buildandburn down {env_id}")
        
        # Return success
        return True
    except Exception as e:
        print_error(f"Failed during environment setup: {str(e)}")
        print_warning("Infrastructure may have been provisioned but deployment failed.")
        print_info(f"You can destroy this environment with: buildandburn down {env_id}")
        return False

def cmd_down(args):
    """Destroy a build-and-burn environment."""
    env_id = args.env_id
    print_info(f"Destroying environment with ID: {env_id}")
    
    # Get environment directory
    env_dir = os.path.join(os.path.expanduser("~"), ".buildandburn", env_id)
    if not os.path.exists(env_dir):
        print_error(f"Environment with ID {env_id} not found.")
        return False
    
    # Load environment info
    env_info_file = os.path.join(env_dir, "env_info.json")
    if not os.path.exists(env_info_file):
        print_error(f"Environment info file not found for ID {env_id}.")
        return False
    
    with open(env_info_file, 'r') as f:
        env_info = json.load(f)
    
    # Get terraform directory
    terraform_dir = os.path.join(env_dir, "terraform")
    if not os.path.exists(terraform_dir):
        print_error(f"Terraform directory not found for environment ID {env_id}.")
        return False
    
    # Verify state file exists
    state_file = env_info.get("state_file")
    if not state_file or not os.path.exists(state_file):
        # First check in the terraform/state directory
        state_file = os.path.join(terraform_dir, "state", "terraform.tfstate")
        if not os.path.exists(state_file):
            # Then check directly in the terraform directory
            state_file = os.path.join(terraform_dir, "terraform.tfstate")
            if not os.path.exists(state_file):
                # Finally check in the legacy location
                state_dir = os.path.join(env_dir, "terraform_state")
                state_file = os.path.join(state_dir, "terraform.tfstate")
                if not os.path.exists(state_file):
                    print_warning(f"State file not found. Trying to use default state.")
                    state_file = os.path.join(terraform_dir, "state", "terraform.tfstate")
                    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    
    print_info(f"Using state file: {state_file}")
    
    # Check state file is valid and fix if needed
    if ensure_valid_state_file(state_file, terraform_dir):
        print_info("State file was in invalid format and has been fixed.")
    
    # Check state file contents
    try:
        with open(state_file, 'r') as f:
            state_content = f.read()
            if state_content.strip() == "{}" or state_content.strip() == "":
                print_warning("State file appears to be empty. No resources to destroy.")
                if input("Continue anyway? (y/N): ").lower() != 'y':
                    print_info("Exiting.")
                    return False
    except Exception as e:
        print_warning(f"Could not read state file: {str(e)}")
    
    # Check if there's a tfvars file
    tf_vars_file = os.path.join(terraform_dir, "terraform.tfvars.json")
    if not os.path.exists(tf_vars_file):
        # Try legacy location
        tf_vars_file = os.path.join(env_dir, "terraform.tfvars.json")
        if not os.path.exists(tf_vars_file):
            print_warning(f"Terraform variables file not found. Will attempt to destroy without it.")
            tf_vars_file = None
    
    # Create destroy plan first
    destroy_plan_file = os.path.join(env_dir, "terraform.destroy.plan")
    print_info("Creating destruction plan...")
    
    # Set up the destroy log file
    tf_destroy_log = os.path.join(env_dir, "terraform_destroy.log")
    print_info(f"Logging detailed Terraform destroy output to: {tf_destroy_log}")
    
    # Create a separate raw output log file for the destroy process
    raw_destroy_log = os.path.join(env_dir, "terraform_destroy_raw.log")
    
    # First create a destroy plan
    try:
        with open(tf_destroy_log, 'w') as log_file:
            log_file.write("=" * 80 + "\n")
            log_file.write("TERRAFORM DESTROY LOG\n")
            log_file.write("=" * 80 + "\n")
            log_file.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Environment ID: {env_id}\n")
            log_file.write(f"Project Name: {env_info.get('project_name', 'Unknown')}\n")
            log_file.write(f"State File: {state_file}\n\n")
            
            # Verify terraform is initialized with the correct state
            print_info("Ensuring Terraform is initialized with the correct state...")
            log_file.write("Ensuring Terraform is initialized with the correct state...\n")
            
            # Create or update backend override to point to the state file
            backend_file = os.path.join(terraform_dir, "backend_override.tf")
            with open(backend_file, 'w') as f:
                f.write(f"""
# Override backend to use the existing state file
terraform {{
  backend "local" {{
    path = "{state_file}"
  }}
}}
""")
            
            # Initialize terraform with the backend config
            init_cmd = "terraform init -reconfigure"
            print_info(f"Running: {init_cmd}")
            log_file.write(f"Initializing Terraform: {init_cmd}\n")
            init_process = subprocess.run(
                init_cmd,
                cwd=terraform_dir,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if init_process.returncode != 0:
                print_error("Failed to initialize Terraform with state file.")
                print_error(init_process.stderr)
                log_file.write(f"Init failed: {init_process.stderr}\n")
                print_warning("Will try to continue with destroy plan, but it may fail.")
            else:
                print_success("Terraform initialized successfully with state file.")
                log_file.write("Terraform initialized successfully.\n")
            
            # Create the destroy plan
            plan_cmd = f"terraform plan -destroy -out='{destroy_plan_file}'"
            if tf_vars_file:
                plan_cmd += f" -var-file='{tf_vars_file}'"
                
            print_info(f"Running: {plan_cmd}")
            log_file.write(f"Creating destroy plan: {plan_cmd}\n")
            
            # Execute the plan command
            plan_process = subprocess.Popen(
                plan_cmd,
                cwd=terraform_dir,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process output in real-time
            for line in plan_process.stdout:
                sys.stdout.write(line)
                log_file.write(line)
            
            # Wait for completion and check for errors
            plan_process.wait()
            stderr_output = plan_process.stderr.read()
            
            if stderr_output:
                print_error("Terraform destroy plan encountered errors:")
                print_error(stderr_output)
                log_file.write("\nERROR OUTPUT:\n")
                log_file.write(stderr_output)
            
            if plan_process.returncode != 0:
                print_error("Failed to create destroy plan.")
                log_file.write("Failed to create destroy plan.\n")
                print_warning("Proceeding with direct destroy command...")
                log_file.write("Proceeding with direct destroy command...\n")
                
                # If plan fails, use direct destroy
                if not args.auto_approve and input("Do you want to proceed with destroying resources? (y/N): ").lower() != 'y':
                    print_info("Destroy cancelled by user.")
                    return False
                
                # Run destroy directly with auto-approve
                destroy_cmd = "terraform destroy -auto-approve"
                if tf_vars_file:
                    destroy_cmd += f" -var-file='{tf_vars_file}'"
                
                print_info(f"Running: {destroy_cmd}")
                log_file.write(f"Running direct destroy: {destroy_cmd}\n")
                
                # Execute direct destroy
                destroy_process = subprocess.Popen(
                    destroy_cmd,
                    cwd=terraform_dir,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Setup for monitoring with timeout
                start_time = time.time()
                last_activity_time = start_time
                last_progress_update = start_time
                timeout = CONFIG["TERRAFORM_DESTROY_TIMEOUT"]
                destroying_resources = set()
                
                print_info(f"Terraform destroy timeout set to {timeout} seconds")
                
                # Process output with timeout monitoring
                while True:
                    # Check for timeout
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    
                    # Provide periodic progress updates
                    if current_time - last_progress_update > CONFIG["PROGRESS_UPDATE_INTERVAL"]:
                        print_info(f"Terraform destroy in progress... ({int(elapsed_time)}s elapsed)")
                        if destroying_resources:
                            print_info(f"Current resources being destroyed: {', '.join(destroying_resources)}")
                        last_progress_update = current_time
                    
                    # Check if process finished
                    if destroy_process.poll() is not None:
                        break
                    
                    # Check for timeout
                    if elapsed_time > timeout:
                        # Try to intelligently handle the timeout
                        time_since_last_activity = current_time - last_activity_time
                        if time_since_last_activity > 300:  # No activity for 5 minutes
                            # Check for specific resources that might be stuck
                            stuck_resources = list(destroying_resources)
                            
                            if stuck_resources:
                                print_warning(f"The following resources appear to be stuck: {', '.join(stuck_resources)}")
                                
                                # For some resources, we know retrying can help
                                retry_resources = [r for r in stuck_resources if any(x in r.lower() for x in ["eks", "kafka", "mq", "rds", "iam"])]
                                
                                if retry_resources and elapsed_time < (timeout * 0.8):
                                    print_info(f"Attempting to continue with {', '.join(retry_resources)}...")
                                    # Reset activity timer to give more time
                                    last_activity_time = current_time
                                    continue
                        
                        # If we reach here, we need to terminate
                        print_error(f"Terraform destroy timed out after {timeout} seconds")
                        apply_process.terminate()
                        try:
                            apply_process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            apply_process.kill()
                        
                        log_file.write(f"\nProcess timed out after {timeout} seconds\n")
                        print_warning("Some resources may still exist in your AWS account.")
                        print_info("You may need to manually clean up resources.")
                        return False
                    
                    # Check if output is available (non-blocking)
                    line = ""
                    try:
                        line = destroy_process.stdout.readline()
                    except Exception as e:
                        print_warning(f"Error reading terraform output: {str(e)}")
                        time.sleep(1)
                        continue
                    
                    if not line:
                        # No output available, wait a bit
                        time.sleep(0.1)
                        continue
                    
                    # Got output, update last activity time
                    last_activity_time = current_time
                    
                    # Write to logs
                    sys.stdout.write(line)
                    log_file.write(line)
                    
                    # Track resources being destroyed
                    if "Destroying..." in line:
                        resource_type = line.split("Destroying...")[0].strip()
                        if resource_type.startswith('"') and resource_type.endswith('"'):
                            resource_type = resource_type[1:-1]
                        destroying_resources.add(resource_type)
                    elif "Destruction complete" in line:
                        for rt in destroying_resources.copy():
                            if rt in line:
                                destroying_resources.remove(rt)
                                break
                
                # Process has finished or timed out
                elapsed_time = time.time() - start_time
                print_info(f"Terraform destroy process finished after {int(elapsed_time)}s")
                
                # Get stderr content
                direct_stderr = destroy_process.stderr.read()
                
                if direct_stderr:
                    print_error("Terraform destroy encountered errors:")
                    print_error(direct_stderr)
                    log_file.write("\nDIRECT DESTROY ERROR OUTPUT:\n")
                    log_file.write(direct_stderr)
                
                if destroy_process.returncode != 0:
                    print_error("Terraform destroy failed.")
                    log_file.write("Terraform destroy failed.\n")
                    print_warning("Some resources may still exist in your AWS account.")
                    print_info("You may need to manually clean up resources.")
                    return False
                else:
                    print_success("Terraform destroy completed successfully.")
                    log_file.write("Terraform destroy completed successfully.\n")
            else:
                # Plan succeeded, now confirm and apply
                if not args.auto_approve and input("Do you want to proceed with destroying resources? (y/N): ").lower() != 'y':
                    print_info("Destroy cancelled by user.")
                    return False
                
                # Apply the destroy plan
                print_info("Applying destroy plan...")
                log_file.write("Applying destroy plan...\n")
                
                apply_cmd = f"terraform apply '{destroy_plan_file}'"
                print_info(f"Running: {apply_cmd}")
                log_file.write(f"Executing: {apply_cmd}\n")
                
                # Execute apply with timeout
                apply_process = subprocess.Popen(
                    apply_cmd,
                    cwd=terraform_dir,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Setup for monitoring with timeout
                start_time = time.time()
                last_activity_time = start_time
                last_progress_update = start_time
                timeout = CONFIG["TERRAFORM_DESTROY_TIMEOUT"]
                destroying_resources = set()
                
                print_info(f"Terraform destroy timeout set to {timeout} seconds")
                
                # Process output with timeout monitoring
                while True:
                    # Check for timeout
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    
                    # Provide periodic progress updates
                    if current_time - last_progress_update > CONFIG["PROGRESS_UPDATE_INTERVAL"]:
                        print_info(f"Terraform destroy in progress... ({int(elapsed_time)}s elapsed)")
                        if destroying_resources:
                            print_info(f"Current resources being destroyed: {', '.join(destroying_resources)}")
                        last_progress_update = current_time
                    
                    # Check if process finished
                    if apply_process.poll() is not None:
                        break
                    
                    # Check for timeout
                    if elapsed_time > timeout:
                        # Try to intelligently handle the timeout
                        time_since_last_activity = current_time - last_activity_time
                        if time_since_last_activity > 300:  # No activity for 5 minutes
                            # Check for specific resources that might be stuck
                            stuck_resources = list(destroying_resources)
                            
                            if stuck_resources:
                                print_warning(f"The following resources appear to be stuck: {', '.join(stuck_resources)}")
                                
                                # For some resources, we know retrying can help
                                retry_resources = [r for r in stuck_resources if any(x in r.lower() for x in ["eks", "kafka", "mq", "rds", "iam"])]
                                
                                if retry_resources and elapsed_time < (timeout * 0.8):
                                    print_info(f"Attempting to continue with {', '.join(retry_resources)}...")
                                    # Reset activity timer to give more time
                                    last_activity_time = current_time
                                    continue
                        
                        # If we reach here, we need to terminate
                        print_error(f"Terraform destroy timed out after {timeout} seconds")
                        apply_process.terminate()
                        try:
                            apply_process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            apply_process.kill()
                        
                        log_file.write(f"\nProcess timed out after {timeout} seconds\n")
                        print_warning("Some resources may still exist in your AWS account.")
                        print_info("You may need to manually clean up resources.")
                        return False
                    
                    # Check if output is available (non-blocking)
                    line = ""
                    try:
                        line = apply_process.stdout.readline()
                    except Exception as e:
                        print_warning(f"Error reading terraform output: {str(e)}")
                        time.sleep(1)
                        continue
                    
                    if not line:
                        # No output available, wait a bit
                        time.sleep(0.1)
                        continue
                    
                    # Got output, update last activity time
                    last_activity_time = current_time
                    
                    # Write to logs
                    sys.stdout.write(line)
                    log_file.write(line)
                    
                    # Track resources being destroyed
                    if "Destroying..." in line:
                        resource_type = line.split("Destroying...")[0].strip()
                        if resource_type.startswith('"') and resource_type.endswith('"'):
                            resource_type = resource_type[1:-1]
                        destroying_resources.add(resource_type)
                    elif "Destruction complete" in line:
                        for rt in destroying_resources.copy():
                            if rt in line:
                                destroying_resources.remove(rt)
                                break
                
                # Process has finished or timed out
                elapsed_time = time.time() - start_time
                print_info(f"Terraform destroy process finished after {int(elapsed_time)}s")
                
                # Check stderr for errors
                apply_stderr = apply_process.stderr.read()
                
                if apply_stderr:
                    print_error("Terraform destroy encountered errors:")
                    print_error(apply_stderr)
                    log_file.write("\nAPPLY ERROR OUTPUT:\n")
                    log_file.write(apply_stderr)
                
                if apply_process.returncode != 0:
                    print_error("Terraform destroy failed.")
                    log_file.write("Terraform destroy failed.\n")
                    print_warning("Some resources may still exist in your AWS account.")
                    print_info("You may need to manually clean up resources.")
                    return False
                else:
                    print_success("Terraform destroy completed successfully.")
                    log_file.write("Terraform destroy completed successfully.\n")
    except Exception as e:
        print_error(f"Error during destroy process: {str(e)}")
        print_warning("Some resources may still exist in your AWS account.")
        print_info("You may need to manually clean up resources.")
        return False
    
    # Clean up local files if requested
    if not args.keep_local:
        print_info("Cleaning up local environment files...")
        try:
            shutil.rmtree(env_dir)
            print_success("Local environment files removed.")
        except Exception as e:
            print_warning(f"Failed to clean up local environment files: {str(e)}")
    else:
        print_info("Keeping local environment files as requested.")
    
    print_success(f"Environment {env_id} destroyed successfully.")
    return True

def cmd_info(args):
    """Get information about an environment."""
    env_id = args.env_id
    
    # Get environment directory
    env_dir = os.path.join(os.path.expanduser("~"), ".buildandburn", env_id)
    if not os.path.exists(env_dir):
        print_error(f"Environment with ID {env_id} not found.")
        return False
    
    # Load environment info
    env_info_file = os.path.join(env_dir, "env_info.json")
    if not os.path.exists(env_info_file):
        print_error(f"Environment info file not found for ID {env_id}.")
        return False
    
    try:
        with open(env_info_file, 'r') as f:
            env_info = json.load(f)
        
        # Display information
        print_info("=" * 80)
        print_info(f"ENVIRONMENT INFORMATION - {env_id}")
        print_info("=" * 80)
        
        # Basic information
        print_info(f"Project Name: {env_info.get('project_name', 'Unknown')}")
        print_info(f"Created At:   {env_info.get('created_at', 'Unknown')}")
        if 'destroyed_at' in env_info:
            print_info(f"Destroyed At: {env_info.get('destroyed_at', 'Unknown')}")
            print_warning("This environment has been destroyed.")
        
        # Access Information - Show this prominently
        if 'access_info' in env_info:
            access_info = env_info['access_info']
            
            # Show the primary URL most prominently if available
            if 'primary_url' in access_info:
                print_info("\n" + "=" * 80)
                print_success(f"APPLICATION URL: {access_info['primary_url']}")
                print_info("=" * 80)
            
            print_info("\nAccess Information:")
            
            # Show ingress information
            if access_info.get('ingresses'):
                print_info("\nIngress URLs:")
                for name, url in access_info['ingresses'].items():
                    print_info(f"- {name}: {url}")
            
            # Show service information
            if access_info.get('services'):
                print_info("\nService Endpoints:")
                for name, endpoint in access_info['services'].items():
                    print_info(f"- {name}: {endpoint}")
            
            # Show database information
            if access_info.get('database'):
                print_info("\nDatabase:")
                print_info(f"- Endpoint: {access_info['database'].get('endpoint', 'Unknown')}")
                print_info(f"- Username: {access_info['database'].get('username', 'Unknown')}")
            
            # Show message queue information
            if access_info.get('message_queue'):
                print_info("\nMessage Queue:")
                print_info(f"- Endpoint: {access_info['message_queue'].get('endpoint', 'Unknown')}")
                print_info(f"- Username: {access_info['message_queue'].get('username', 'Unknown')}")
            
            # Show Redis information
            if access_info.get('redis'):
                print_info("\nRedis:")
                print_info(f"- Primary Endpoint: {access_info['redis'].get('primary_endpoint', 'Unknown')}")
                if access_info['redis'].get('reader_endpoint'):
                    print_info(f"- Reader Endpoint: {access_info['redis'].get('reader_endpoint', 'Unknown')}")
                print_info(f"- Port: {access_info['redis'].get('port', '6379')}")
        
        # AWS information
        print_info("\nAWS Details:")
        print_info(f"Region:      {env_info.get('region', 'Unknown')}")
        
        # Resource information
        if 'resources' in env_info:
            total_cost = env_info.get('estimated_cost_per_hour', 0)
            print_info("\nProvisioned Resources:")
            for resource in env_info.get('resources', []):
                print_info(f"- {resource.get('count', '?')} x {resource.get('type', 'Unknown')} ({resource.get('name', 'Unknown')})")
            
            print_info(f"\nEstimated Cost: ${total_cost}/hour (${total_cost * 24 * 30}/month)")
        
        # Terraform output
        if 'terraform_output' in env_info and env_info['terraform_output']:
            print_info("\nTerraform Outputs:")
            for key, value in env_info['terraform_output'].items():
                if 'value' in value and 'sensitive' in value and not value['sensitive']:
                    print_info(f"- {key}: {value['value']}")
        
        # Working directories
        print_info("\nEnvironment Directories:")
        print_info(f"State File:        {env_info.get('state_file', 'Unknown')}")
        print_info(f"Terraform Dir:     {env_info.get('terraform_dir', 'Unknown')}")
        print_info(f"Working Dir:       {env_info.get('working_dir', 'Unknown')}")
        
        # Command for destruction
        if 'destroyed_at' not in env_info:
            print_info("\nTo destroy this environment, run:")
            print_info(f"buildandburn down {env_id}")
        
        return True
    except Exception as e:
        print_error(f"Error reading environment information: {str(e)}")
        return False

def cmd_list(args):
    """List all environments."""
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENTS")
    print_info("=" * 80)
    
    # Get buildandburn directory
    bb_dir = os.path.join(os.path.expanduser("~"), ".buildandburn")
    if not os.path.exists(bb_dir):
        print_warning("No environments found.")
        return True
    
    # Get all environment directories
    env_dirs = [d for d in os.listdir(bb_dir) if os.path.isdir(os.path.join(bb_dir, d))]
    if not env_dirs:
        print_warning("No environments found.")
        return True
    
    # Sort by creation time if available
    env_info_list = []
    for env_id in env_dirs:
        env_dir = os.path.join(bb_dir, env_id)
        env_info_file = os.path.join(env_dir, "env_info.json")
        
        if os.path.exists(env_info_file):
            try:
                with open(env_info_file, 'r') as f:
                    env_info = json.load(f)
                # Add environment info to list
                env_info['env_id'] = env_id
                env_info_list.append(env_info)
            except Exception as e:
                # If we can't read the info file, create a minimal entry
                env_info_list.append({
                    'env_id': env_id,
                    'project_name': 'Unknown',
                    'created_at': 'Unknown',
                    'error': str(e)
                })
    
    # Sort by creation time, most recent first
    try:
        env_info_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    except Exception:
        # If sorting fails, don't bother
        pass
    
    # Print table header
    print(f"{'ID':<12} {'Project':<20} {'Created':<20} {'Status':<10} {'Region':<10}")
    print("-" * 75)
    
    # Print environments
    for env_info in env_info_list:
        env_id = env_info.get('env_id', 'Unknown')
        project_name = env_info.get('project_name', 'Unknown')
        created_at = env_info.get('created_at', 'Unknown')
        status = "DESTROYED" if 'destroyed_at' in env_info else "ACTIVE"
        region = env_info.get('region', 'Unknown')
        
        print(f"{env_id:<12} {project_name:<20} {created_at:<20} {status:<10} {region:<10}")
    
    print("\nTo get information about a specific environment, run:")
    print("buildandburn info ENV_ID")
    
    print("\nTo destroy a specific environment, run:")
    print("buildandburn down ENV_ID")
    
    return True

def ensure_valid_state_file(state_file_path, terraform_dir=None):
    """
    Check if a state file exists and is in valid format.
    If not, create or update it with proper format.
    """
    try:
        # Check if the file exists and read its content
        if not os.path.exists(state_file_path):
            create_valid_state_file(state_file_path, terraform_dir)
            return True
            
        with open(state_file_path, 'r') as f:
            content = f.read().strip()
            
        # Check if it's empty or just {}
        if not content or content == "{}":
            print_warning(f"State file at {state_file_path} has invalid format. Fixing...")
            create_valid_state_file(state_file_path, terraform_dir)
            return True
            
        # Check if it's valid JSON with version
        try:
            state_data = json.loads(content)
            if "version" not in state_data:
                print_warning(f"State file at {state_file_path} is missing version attribute. Fixing...")
                create_valid_state_file(state_file_path, terraform_dir)
                return True
        except json.JSONDecodeError:
            print_warning(f"State file at {state_file_path} is not valid JSON. Fixing...")
            create_valid_state_file(state_file_path, terraform_dir)
            return True
            
        # State file appears to be valid
        return False
        
    except Exception as e:
        print_error(f"Error checking state file: {str(e)}")
        # Try to create a valid state file anyway
        create_valid_state_file(state_file_path, terraform_dir)
        return True
        

def create_valid_state_file(state_file_path, terraform_dir=None):
    """Create a properly formatted Terraform state file."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        
        # Try to get terraform version if terraform_dir is provided
        terraform_version_str = "1.0.0"  # Default version
        if terraform_dir and os.path.exists(terraform_dir):
            try:
                terraform_version = subprocess.run(
                    "terraform version -json",
                    cwd=terraform_dir,
                    shell=True,
                    capture_output=True,
                    text=True
                ).stdout.strip()
                
                # Extract the version
                terraform_version_obj = json.loads(terraform_version)
                terraform_version_str = terraform_version_obj.get("terraform_version", "1.0.0")
            except:
                # If we can't get the version, use the default
                pass
        
        # Create a properly formatted state file
        state_content = {
            "version": 4,
            "terraform_version": terraform_version_str,
            "serial": 0,
            "lineage": str(uuid.uuid4()),
            "outputs": {},
            "resources": []
        }
        
        with open(state_file_path, 'w') as f:
            json.dump(state_content, f, indent=2)
            
        print_success(f"Created properly formatted state file at: {state_file_path}")
        return True
    except Exception as e:
        print_error(f"Failed to create valid state file: {str(e)}")
        return False

def fix_terraform_issues(terraform_dir, error_analysis, tf_vars_file=None, region=None):
    """Automatically fix common Terraform issues based on error analysis."""
    if not error_analysis["auto_fix_possible"]:
        print_warning("No automatic fixes available for the detected issues.")
        return False
    
    fixes_applied = []
    
    for action in error_analysis["fix_actions"]:
        if action == "add_provider_config":
            if add_provider_config(terraform_dir, region):
                fixes_applied.append("Added AWS provider configuration")
        
        elif action == "reinit_upgrade":
            if reinit_terraform_with_upgrade(terraform_dir):
                fixes_applied.append("Reinitialized Terraform with provider upgrades")
        
        elif action == "check_required_vars":
            if check_and_fix_required_vars(terraform_dir, tf_vars_file, region):
                fixes_applied.append("Added missing required variables")
        
        elif action == "fix_duplicate_providers":
            if fix_duplicate_provider_blocks(terraform_dir):
                fixes_applied.append("Fixed duplicate provider blocks")
        
        elif action == "clear_plugin_cache":
            if clear_terraform_plugin_cache(terraform_dir):
                fixes_applied.append("Cleared Terraform plugin cache")
        
        elif action == "auto_format":
            if auto_format_terraform_files(terraform_dir):
                fixes_applied.append("Auto-formatted Terraform files")
    
    if fixes_applied:
        print_success(f"Applied fixes: {', '.join(fixes_applied)}")
        return True
    
    return False

def add_provider_config(terraform_dir, region=None):
    """Add a proper AWS provider configuration to the Terraform files."""
    try:
        # Check if providers.tf already exists
        providers_file = os.path.join(terraform_dir, "providers.tf")
        
        # If it doesn't exist, create it
        if not os.path.exists(providers_file):
            if not region:
                region = "us-west-2"  # Default region
            
            with open(providers_file, 'w') as f:
                f.write(f'''# AWS Provider Configuration
provider "aws" {{
  region = "{region}"
}}
''')
            print_success(f"Created providers.tf with AWS provider configuration")
            return True
        
        # If it exists, check if it has AWS provider configuration
        with open(providers_file, 'r') as f:
            content = f.read()
        
        if 'provider "aws"' not in content:
            # Add AWS provider configuration
            if not region:
                region = "us-west-2"  # Default region
            
            with open(providers_file, 'a') as f:
                f.write(f'''
# AWS Provider Configuration
provider "aws" {{
  region = "{region}"
}}
''')
            print_success(f"Added AWS provider configuration to existing providers.tf")
            return True
        
        return False  # No changes needed
    except Exception as e:
        print_error(f"Failed to fix provider configuration: {str(e)}")
        return False

def reinit_terraform_with_upgrade(terraform_dir):
    """Reinitialize Terraform with upgrade flag to refresh providers."""
    try:
        print_info("Reinitializing Terraform with provider upgrades...")
        result = run_command(["terraform", "init", "-upgrade"], cwd=terraform_dir, capture_output=True)
        print_success("Successfully reinitialized Terraform with provider upgrades")
        return True
    except Exception as e:
        print_error(f"Failed to reinitialize Terraform: {str(e)}")
        return False

def check_and_fix_required_vars(terraform_dir, tf_vars_file, region=None):
    """Check for required variables and add defaults to tfvars file."""
    if not tf_vars_file:
        print_warning("No tfvars file provided, cannot fix missing variables")
        return False
    
    try:
        # Use terraform-config-inspect to find required variables
        vars_check_cmd = ["terraform-config-inspect", "--json", "."]
        try:
            vars_process = run_command(vars_check_cmd, cwd=terraform_dir, capture_output=True, allow_fail=True)
            vars_data = json.loads(vars_process.stdout)
            required_vars = []
            
            # Find required variables
            for var in vars_data.get("variables", []):
                if not var.get("default") and not var.get("required", False):
                    required_vars.append(var.get("name"))
            
            # Check if all required variables are in our tfvars file
            with open(tf_vars_file, 'r') as f:
                tfvars_data = json.load(f)
            
            missing_vars = []
            for var in required_vars:
                if var not in tfvars_data:
                    missing_vars.append(var)
            
            if missing_vars:
                print_warning(f"Missing required variables: {', '.join(missing_vars)}")
                print_info("Updating tfvars file with defaults for missing variables...")
                
                # Add default values for missing variables
                for var in missing_vars:
                    # Set some sensible defaults based on variable name patterns
                    if "region" in var and region:
                        tfvars_data[var] = region
                    elif var == "project_name":
                        tfvars_data[var] = "buildandburn-project"
                    elif var == "env_id":
                        tfvars_data[var] = "dev"
                    else:
                        # Generic default based on type
                        tfvars_data[var] = ""  # Empty string as default
                
                # Save updated tfvars
                with open(tf_vars_file, 'w') as f:
                    json.dump(tfvars_data, f, indent=2)
                return True
            
            return False  # No missing variables
        except:
            print_warning("terraform-config-inspect not available, skipping variable checking")
            return False
    except Exception as e:
        print_error(f"Failed to check and fix variables: {str(e)}")
        return False

def fix_duplicate_provider_blocks(terraform_dir):
    """Fix duplicate provider blocks in Terraform files."""
    try:
        # Find all provider blocks in all Terraform files
        provider_files = {}
        tf_files = glob.glob(os.path.join(terraform_dir, "*.tf"))
        
        for tf_file in tf_files:
            with open(tf_file, 'r') as f:
                content = f.read()
            
            # Check for provider blocks
            if 'provider "aws"' in content:
                if "providers.tf" not in provider_files:
                    provider_files["providers.tf"] = []
                provider_files["providers.tf"].append(tf_file)
        
        # If we have duplicate provider blocks, fix them
        if "providers.tf" in provider_files and len(provider_files["providers.tf"]) > 1:
            print_warning(f"Found duplicate AWS provider blocks in {len(provider_files['providers.tf'])} files")
            
            # Keep provider block only in providers.tf
            for tf_file in provider_files["providers.tf"]:
                if os.path.basename(tf_file) != "providers.tf":
                    with open(tf_file, 'r') as f:
                        content = f.read()
                    
                    # Extract the provider block and remove it
                    provider_pattern = r'provider\s+"aws"\s+\{[^}]*\}'
                    new_content = re.sub(provider_pattern, '', content)
                    
                    with open(tf_file, 'w') as f:
                        f.write(new_content)
            
            print_success("Removed duplicate AWS provider blocks")
            return True
        
        return False  # No duplicate provider blocks
    except Exception as e:
        print_error(f"Failed to fix duplicate provider blocks: {str(e)}")
        return False

def clear_terraform_plugin_cache(terraform_dir):
    """Clear Terraform plugin cache to fix provider issues."""
    try:
        # Remove .terraform directory
        terraform_plugins_dir = os.path.join(terraform_dir, ".terraform")
        if os.path.exists(terraform_plugins_dir):
            print_info(f"Removing Terraform plugin cache directory: {terraform_plugins_dir}")
            shutil.rmtree(terraform_plugins_dir, ignore_errors=True)
        
        # Remove .terraform.lock.hcl file
        lock_file = os.path.join(terraform_dir, ".terraform.lock.hcl")
        if os.path.exists(lock_file):
            print_info(f"Removing Terraform lock file: {lock_file}")
            os.remove(lock_file)
        
        print_success("Cleared Terraform plugin cache")
        
        # Try reinitialization
        print_info("Reinitializing Terraform...")
        init_cmd = ["terraform", "init"]
        run_command(init_cmd, cwd=terraform_dir, capture_output=True)
        
        return True
    except Exception as e:
        print_error(f"Failed to clear Terraform plugin cache: {str(e)}")
        return False

def auto_format_terraform_files(terraform_dir):
    """Auto-format Terraform files to fix syntax issues."""
    try:
        print_info("Auto-formatting Terraform files...")
        fmt_cmd = ["terraform", "fmt", "-recursive"]
        result = run_command(fmt_cmd, cwd=terraform_dir, capture_output=True, allow_fail=True)
        
        if result.returncode == 0:
            print_success("Successfully formatted Terraform files")
            return True
        else:
            print_warning("Terraform fmt failed. Some files may have syntax errors that cannot be automatically fixed.")
            return False
    except Exception as e:
        print_error(f"Failed to format Terraform files: {str(e)}")
        return False

def ensure_k8s_resources(manifest, k8s_dir, project_dir, auto_generate=True):
    """Ensure Kubernetes resource files exist, generate them if not and if auto_generate is enabled.
    
    Args:
        manifest: The manifest dict
        k8s_dir: The default k8s directory
        project_dir: The project directory
        auto_generate: Whether to auto-generate resources if none exist (default: True)
        
    Returns:
        The path to the k8s resources to use
    """
    print_info("Checking for Kubernetes resources...")
    
    # Define paths to check
    helm_chart_path = os.path.join(k8s_dir, "chart")
    manifests_path = os.path.join(k8s_dir, "manifests")
    
    # Check if any are custom-defined in the manifest
    custom_k8s_path = None
    if 'k8s_path' in manifest:
        custom_k8s_path = os.path.abspath(manifest['k8s_path'])
        print_info(f"Custom k8s path specified in manifest: {custom_k8s_path}")
        
        if os.path.exists(custom_k8s_path):
            print_info(f"Using user-provided Kubernetes resources from: {custom_k8s_path}")
            return custom_k8s_path
        else:
            print_warning(f"Specified k8s_path '{custom_k8s_path}' does not exist.")
    
    # Check for helm chart or manifests in standard locations
    has_helm_chart = os.path.exists(os.path.join(helm_chart_path, "Chart.yaml"))
    has_manifests = os.path.exists(manifests_path) and any(f.endswith(('.yaml', '.yml')) for f in os.listdir(manifests_path)) if os.path.exists(manifests_path) else False
    
    # If standard resources exist, use them
    if has_helm_chart:
        print_info(f"Using existing Helm chart from: {helm_chart_path}")
        return k8s_dir
    elif has_manifests:
        print_info(f"Using existing Kubernetes manifests from: {manifests_path}")
        return k8s_dir
    
    # If nothing exists and auto_generate is disabled, return the default k8s_dir
    if not auto_generate:
        print_info("No Kubernetes resources found and auto-generation is disabled. Using default paths.")
        return k8s_dir
    
    # Check if the k8s_generator module is available
    if not k8s_generator_available:
        print_warning("K8s generator module not available, skipping resource generation.")
        return k8s_dir
    
    # If no resources exist and auto_generate is enabled, generate resources
    print_info("No Kubernetes resources found. Generating from manifest...")
    generated_dir = os.path.join(project_dir, "generated_k8s")
    
    # Generate both Helm chart and raw manifests
    try:
        k8s_generator.generate_manifests(manifest, os.path.join(generated_dir, "manifests"))
        k8s_generator.create_helm_chart(manifest, generated_dir)
        
        print_success("Generated Kubernetes resources successfully.")
        print_info(f"Helm chart: {os.path.join(generated_dir, 'chart')}")
        print_info(f"Manifests: {os.path.join(generated_dir, 'manifests')}")
        
        # Set the k8s_dir to the generated directory
        return generated_dir
    except Exception as e:
        print_warning(f"Failed to generate Kubernetes resources: {str(e)}")
        traceback.print_exc()
        return k8s_dir

def validate_terraform_modules_against_manifest(manifest, terraform_project_dir):
    """
    Validate Terraform modules against the manifest requirements.
    Checks if all required modules are available for the dependencies specified in the manifest.
    
    Args:
        manifest (dict): The parsed manifest
        terraform_project_dir (str): Path to the terraform project directory
        
    Returns:
        tuple: (is_valid, validation_results)
            is_valid: boolean indicating if validation passed
            validation_results: dict with detailed validation results
    """
    print_color("\n===============================================================================", "34")
    print_color("VALIDATING TERRAFORM MODULES AGAINST MANIFEST", "34")
    print_color("===============================================================================", "34")
    
    validation_results = {
        "success": True,
        "modules": {
            "required": [],
            "missing": [],
            "available": [],
        },
        "policy_modules": {
            "required": [],
            "missing": [],
            "available": [],
        },
        "access_policy_modules": {
            "required": [],
            "missing": [],
            "available": [],
        },
        "iam_policies": {
            "required": [],
            "missing": [],
            "available": [],
        },
        "dependencies": {
            "required": [],
            "missing": [],
            "connection_issues": []
        },
        "summary": "",
        "next_steps": [],
        "auto_fixable": False,
        "fix_actions": []
    }
    
    # Core modules always required
    required_modules = ["vpc", "eks"]
    
    # Get dependencies from manifest
    dependencies = []
    if 'dependencies' in manifest:
        for dep in manifest['dependencies']:
            dependencies.append(dep['type'])
            validation_results["dependencies"]["required"].append(dep['type'])
    
    print_info(f"Required dependencies from manifest: {', '.join(dependencies) if dependencies else 'none'}")
    
    # Add additional required modules based on dependencies
    if "database" in dependencies:
        required_modules.append("rds")
    
    if "queue" in dependencies:
        required_modules.append("mq")
    
    if "redis" in dependencies:
        required_modules.append("elasticache")
    
    # Define policy modules needed based on dependencies
    required_policy_modules = []
    if "database" in dependencies:
        required_policy_modules.append("eks-to-rds-policy")
        validation_results["policy_modules"]["required"].append("eks-to-rds-policy")
    
    if "queue" in dependencies:
        required_policy_modules.append("eks-to-mq-policy")
        validation_results["policy_modules"]["required"].append("eks-to-mq-policy")
    
    if "redis" in dependencies:
        required_policy_modules.append("eks-to-elasticache-policy")
        validation_results["policy_modules"]["required"].append("eks-to-elasticache-policy")
    
    # Check if core modules exist
    modules_dir = os.path.join(terraform_project_dir, "modules")
    if not os.path.exists(modules_dir):
        print_error("Terraform modules directory not found")
        validation_results["success"] = False
        validation_results["modules"]["missing"] = required_modules
        validation_results["summary"] = "Terraform modules directory not found"
        validation_results["next_steps"].append("Create a modules directory in your Terraform project")
        validation_results["next_steps"].append("Add required modules: " + ", ".join(required_modules))
        return False, validation_results
    
    # Track missing modules
    missing_modules = []
    available_modules = []
    
    # Check each required module
    for module in required_modules:
        validation_results["modules"]["required"].append(module)
        module_path = os.path.join(modules_dir, module)
        
        if not os.path.exists(module_path):
            print_error(f"Required Terraform module '{module}' not found")
            missing_modules.append(module)
            validation_results["modules"]["missing"].append(module)
        else:
            print_success(f"Found required module: {module}")
            available_modules.append(module)
            validation_results["modules"]["available"].append(module)
            
            # Validate module for required files
            required_files = ["main.tf", "variables.tf", "outputs.tf"]
            for file in required_files:
                if not os.path.exists(os.path.join(module_path, file)):
                    print_warning(f"Module '{module}' is missing '{file}'")
    
    # Check policy modules
    missing_policy_modules = []
    available_policy_modules = []
    
    for policy_module in required_policy_modules:
        policy_module_path = os.path.join(modules_dir, policy_module)
        
        if not os.path.exists(policy_module_path):
            print_warning(f"Policy module '{policy_module}' not found but might be needed")
            missing_policy_modules.append(policy_module)
            validation_results["policy_modules"]["missing"].append(policy_module)
        else:
            print_success(f"Found policy module: {policy_module}")
            available_policy_modules.append(policy_module)
            validation_results["policy_modules"]["available"].append(policy_module)
    
    # Analyze module interdependencies
    print_info("Analyzing module dependencies and connections...")
    
    # Example connection checks
    connection_issues = []
    
    # 1. Check if RDS module can connect to EKS
    if "database" in dependencies and "rds" in available_modules and "eks" in available_modules:
        # Check for security group reference in RDS module
        rds_main_tf = os.path.join(modules_dir, "rds", "main.tf")
        if os.path.exists(rds_main_tf):
            with open(rds_main_tf, 'r') as f:
                rds_content = f.read()
                if "eks_security_group_id" not in rds_content:
                    issue = "RDS module may not be able to connect to EKS (eks_security_group_id not used)"
                    print_warning(issue)
                    connection_issues.append(issue)
                    validation_results["dependencies"]["connection_issues"].append(issue)
    
    # 2. Check if MQ module can connect to EKS
    if "queue" in dependencies and "mq" in available_modules and "eks" in available_modules:
        # Check for security group reference in MQ module
        mq_main_tf = os.path.join(modules_dir, "mq", "main.tf")
        if os.path.exists(mq_main_tf):
            with open(mq_main_tf, 'r') as f:
                mq_content = f.read()
                if "eks_security_group_id" not in mq_content:
                    issue = "MQ module may not be able to connect to EKS (eks_security_group_id not used)"
                    print_warning(issue)
                    connection_issues.append(issue)
                    validation_results["dependencies"]["connection_issues"].append(issue)
    
    # Check main.tf for policy module references if missing
    if missing_policy_modules and all(m in available_modules for m in ["eks", "vpc"]):
        main_tf = os.path.join(terraform_project_dir, "main.tf")
        if os.path.exists(main_tf):
            with open(main_tf, 'r') as f:
                main_content = f.read()
                
                # Check if modules declaration exists but not enabled
                for module in missing_policy_modules:
                    module_name = module.replace("-", "_")
                    if f"module \"{module_name}\"" in main_content:
                        print_info(f"Policy module '{module}' is referenced in main.tf but may be commented out or conditionally disabled")
                    else:
                        print_warning(f"Policy module '{module}' is not referenced in main.tf")
                        
                        # Add fix action if module files exist but not referenced
                        module_files_exist = os.path.exists(os.path.join(modules_dir, module))
                        if module_files_exist:
                            validation_results["auto_fixable"] = True
                            validation_results["fix_actions"].append({
                                "type": "add_module_reference",
                                "module": module
                            })
    
    # Check for required IAM policies in eks module
    eks_module_path = os.path.join(modules_dir, "eks")
    eks_policy_issues = []
    
    if os.path.exists(eks_module_path):
        eks_main_tf = os.path.join(eks_module_path, "main.tf")
        if os.path.exists(eks_main_tf):
            with open(eks_main_tf, 'r') as f:
                eks_content = f.read()
                
                iam_policy_checks = {
                    "database": {
                        "policy_name": "AmazonRDSFullAccess",
                        "description": "EKS node role needs access to RDS"
                    },
                    "queue": {
                        "policy_name": "AmazonMQFullAccess",
                        "description": "EKS node role needs access to Amazon MQ"
                    },
                    "redis": {
                        "policy_name": "AmazonElastiCacheFullAccess",
                        "description": "EKS node role needs access to ElastiCache"
                    }
                }
                
                for dep, policy_info in iam_policy_checks.items():
                    if dep in dependencies:
                        validation_results["iam_policies"]["required"].append(policy_info["policy_name"])
                        if policy_info["policy_name"] not in eks_content:
                            issue = f"Missing IAM policy for {dep} dependency: {policy_info['description']}"
                            print_warning(issue)
                            eks_policy_issues.append(issue)
                            validation_results["iam_policies"]["missing"].append(policy_info["policy_name"])
                            
                            # This can be fixed with policy modules
                            if f"eks-to-{dep}-policy" not in available_policy_modules:
                                validation_results["auto_fixable"] = True
                                validation_results["fix_actions"].append({
                                    "type": "add_policy_module",
                                    "module": f"eks-to-{dep}-policy",
                                    "dependency": dep
                                })
                        else:
                            print_success(f"Found IAM policy for {dep} dependency")
                            validation_results["iam_policies"]["available"].append(policy_info["policy_name"])
    
    # Generate summary
    if missing_modules:
        validation_results["success"] = False
        validation_results["summary"] = f"Missing required Terraform modules: {', '.join(missing_modules)}"
        print_error(validation_results["summary"])
        
        # Add next steps
        validation_results["next_steps"].append("Add the following modules to your Terraform project:")
        for module in missing_modules:
            validation_results["next_steps"].append(f"- {module}: Required for {module} infrastructure")
    elif missing_policy_modules:
        # Missing policy modules is a warning, not a failure
        validation_results["success"] = True
        validation_results["summary"] = f"Required Terraform modules found, but missing policy modules: {', '.join(missing_policy_modules)}"
        print_warning(validation_results["summary"])
        
        # Add next steps
        validation_results["next_steps"].append("Add the following policy modules to enable proper service connectivity:")
        for module in missing_policy_modules:
            validation_results["next_steps"].append(f"- {module}: Required for EKS to access dependent services")
            
        # Add auto-fix instructions if possible
        if validation_results["auto_fixable"]:
            validation_results["next_steps"].append("\nThese policy modules can be automatically added. The buildandburn script will attempt to fix this.")
    else:
        validation_results["success"] = True
        validation_results["summary"] = "All required Terraform modules and policy modules are available"
        print_success(validation_results["summary"])
    
    # Add warnings about connection issues
    if connection_issues:
        print_warning("Potential connection issues detected:")
        for issue in connection_issues:
            print_warning(f"- {issue}")
        
        validation_results["next_steps"].append("Address potential connection issues:")
        for issue in connection_issues:
            validation_results["next_steps"].append(f"- {issue}")
    
    if eks_policy_issues:
        print_warning("IAM policy issues detected:")
        for issue in eks_policy_issues:
            print_warning(f"- {issue}")
        
        validation_results["next_steps"].append("Add required IAM policies to EKS node role")
    
    # Print validation summary
    print_info("\nValidation Summary:")
    print_info("-" * 50)
    
    print_info(f"Required modules: {', '.join(validation_results['modules']['required'])}")
    if validation_results["modules"]["missing"]:
        print_error(f"Missing modules: {', '.join(validation_results['modules']['missing'])}")
    else:
        print_success("All required modules are available")
    
    if required_policy_modules:
        print_info(f"Required policy modules: {', '.join(required_policy_modules)}")
        if validation_results["policy_modules"]["missing"]:
            print_warning(f"Missing policy modules: {', '.join(validation_results['policy_modules']['missing'])}")
        else:
            print_success("All required policy modules are available")
    
    # Check for required access policy modules (the new modules we added)
    required_access_policy_modules = validation_results.get("access_policy_modules", {}).get("required", [])
    if required_access_policy_modules:
        print_info(f"Required access policy modules: {', '.join(required_access_policy_modules)}")
        if validation_results.get("access_policy_modules", {}).get("missing", []):
            print_warning(f"Missing access policy modules: {', '.join(validation_results['access_policy_modules']['missing'])}")
        else:
            print_success("All required access policy modules are available")
    
    if validation_results["iam_policies"]["missing"]:
        print_warning(f"Missing IAM policies: {', '.join(validation_results['iam_policies']['missing'])}")
    
    if validation_results["dependencies"]["connection_issues"]:
        print_warning("Connection issues:")
        for issue in validation_results["dependencies"]["connection_issues"]:
            print_warning(f"- {issue}")
    
    if validation_results["next_steps"]:
        print_info("\nRecommended next steps:")
        for i, step in enumerate(validation_results["next_steps"]):
            print_info(f"{i+1}. {step}")
    
    return validation_results["success"], validation_results

def apply_terraform_module_fixes(validation_results, terraform_project_dir):
    """
    Apply fixes for missing policy modules based on validation results.
    
    Args:
        validation_results (dict): Results from validate_terraform_modules_against_manifest
        terraform_project_dir (str): Path to the terraform project directory
        
    Returns:
        bool: True if fixes were applied, False otherwise
    """
    if not validation_results.get("auto_fixable", False) or not validation_results.get("fix_actions"):
        return False
    
    fixed = False
    
    for action in validation_results["fix_actions"]:
        if action["type"] == "add_module_reference":
            # Add module reference to main.tf
            module_name = action["module"]
            module_var_name = module_name.replace("-", "_")
            dependency = None
            
            # Determine which dependency this is for
            if "rds" in module_name:
                dependency = "database"
            elif "mq" in module_name:
                dependency = "queue"
            elif "elasticache" in module_name or "redis" in module_name:
                dependency = "redis"
            
            if dependency:
                try:
                    # Read current main.tf
                    main_tf_path = os.path.join(terraform_project_dir, "main.tf")
                    with open(main_tf_path, 'r') as f:
                        content = f.read()
                    
                    # Create module block to add based on module type
                    if "full-access" in module_name or "write-access" in module_name:
                        # This is an access policy module
                        module_block = f"""
# Conditionally create {module_name} if {dependency} is requested
module "{module_var_name}" {{
  source = "./modules/{module_name}"
  count  = contains(var.dependencies, "{dependency}") ? 1 : 0
  
  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags
  
  depends_on = [module.eks]
}}
"""
                    else:
                        # This is a standard policy module
                        module_block = f"""
# Conditionally create {module_name} if {dependency} is requested
module "{module_var_name}" {{
  source = "./modules/{module_name}"
  count  = contains(var.dependencies, "{dependency}") ? 1 : 0
  
  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags
  
  depends_on = [module.eks]
}}
"""
                    
                    # Find a good position to insert - after all existing modules
                    # Look for the kubernetes provider section which is typically after modules
                    k8s_provider_pos = content.find('provider "kubernetes"')
                    
                    if k8s_provider_pos != -1:
                        # Insert before kubernetes provider
                        new_content = content[:k8s_provider_pos] + module_block + "\n" + content[k8s_provider_pos:]
                        
                        # Write back to file
                        with open(main_tf_path, 'w') as f:
                            f.write(new_content)
                            
                        print_success(f"Added {module_name} module reference to main.tf")
                        fixed = True
                except Exception as e:
                    print_error(f"Failed to add module reference: {str(e)}")
        
        elif action["type"] == "add_policy_module" or action["type"] == "add_access_policy_module":
            # These are handled by the add_module_reference case above
            pass
    
    return fixed

def handle_terraform_timeout(process, resources, current_time, start_time, last_activity_time, timeout, log_file, operation="apply"):
    """Handle Terraform operation timeout with intelligent retry logic.
    
    Args:
        process: The subprocess.Popen object
        resources: Set of resources being operated on
        current_time: Current timestamp
        start_time: Timestamp when the operation started
        last_activity_time: Timestamp of last activity
        timeout: Timeout limit in seconds
        log_file: File handle for logging
        operation: Type of operation, 'apply' or 'destroy'
        
    Returns:
        Tuple of (should_terminate, last_activity_time)
        - should_terminate: True if process should be terminated, False to continue
        - last_activity_time: Updated last activity timestamp if continuing
    """
    elapsed_time = current_time - start_time
    print_error(f"Terraform {operation} timed out after {timeout} seconds")
    
    # Check for specific timeout cases where retrying might help
    time_since_last_activity = current_time - last_activity_time
    if time_since_last_activity > 300:  # No activity for 5 minutes
        print_warning("No activity detected for 5 minutes. This might be a stuck operation.")
        
        # Try to identify stuck resources
        stuck_resources = list(resources)
        
        if stuck_resources:
            print_warning(f"The following resources appear to be stuck: {', '.join(stuck_resources)}")
            
            # For some resources, we know retrying can help
            resource_types = ["eks", "kafka", "mq", "rds", "iam"]
            retry_resources = [r for r in stuck_resources if any(x in r.lower() for x in resource_types)]
            
            if retry_resources and elapsed_time < (timeout * 0.8):  # Only retry if we haven't used most of the timeout
                print_info(f"Attempting to continue with {', '.join(retry_resources)}...")
                # Continue execution and give more time for these specific resources
                return False, current_time  # Don't terminate, update last activity time
    
    # If we reach here, terminate the process
    process.terminate()
    # Wait a bit for process to terminate
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    
    log_file.write(f"\nProcess timed out after {timeout} seconds\n")
    return True, last_activity_time  # Do terminate

def main():
    parser = argparse.ArgumentParser(description='Build and Burn - Create disposable development environments')
    
    # Version information
    parser.add_argument('--version', action='store_true', help='Show version information')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    # Only make command required if version is not provided
    subparsers.required = False
    
    # Up command
    parser_up = subparsers.add_parser('up', help='Create a new environment')
    parser_up.add_argument('-m', '--manifest', required=True, help='Path to the manifest file')
    parser_up.add_argument('-i', '--env-id', help='Environment ID (generated if not provided)')
    parser_up.add_argument('-a', '--auto-approve', action='store_true', help='Auto-approve Terraform operations')
    parser_up.add_argument('--no-generate-k8s', action='store_true', help='Disable automatic generation of Kubernetes resources')
    parser_up.add_argument('--dry-run', action='store_true', help='Validate configuration without creating resources')
    parser_up.add_argument('--skip-module-confirmation', action='store_true', help='Skip confirmation when policy modules or required modules are missing')
    parser_up.set_defaults(func=cmd_up)
    
    # Down command
    parser_down = subparsers.add_parser('down', help='Destroy an environment')
    parser_down.add_argument('env_id', help='Environment ID to destroy')
    parser_down.add_argument('-f', '--force', action='store_true', help='Force destruction even if errors occur')
    parser_down.add_argument('-a', '--auto-approve', action='store_true', help='Auto-approve Terraform destroy operation')
    parser_down.add_argument('-k', '--keep-local', action='store_true', help='Keep local environment files after destroying resources')
    parser_down.set_defaults(func=cmd_down)
    
    # Info command
    parser_info = subparsers.add_parser('info', help='Get information about an environment')
    parser_info.add_argument('env_id', help='Environment ID to get information about')
    parser_info.set_defaults(func=cmd_info)
    
    # List command
    parser_list = subparsers.add_parser('list', help='List all environments')
    parser_list.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    # Handle version flag first
    if args.version:
        print(f"Build and Burn version {__version__}")
        return 0
    
    # If no command was provided and version flag wasn't used, show help
    if not hasattr(args, 'command') or args.command is None:
        parser.print_help()
        return 1
    
    # Check prerequisites before running
    if args.command == 'up':
        prerequisites_ok = check_prerequisites()
        if not prerequisites_ok:
            print_warning("One or more prerequisites are missing.")
            if input("Continue anyway? (y/N): ").lower() != 'y':
                return 1
    
    # Run the selected command
    try:
        success = args.func(args)
        if not success:
            return 1
        return 0
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user.")
        if args.command == 'up':
            print_info("Note: Infrastructure may have been partially created.")
            print_info("You can destroy it with the 'down' command if needed.")
        return 1
    except Exception as e:
        print_error(f"Error executing command: {str(e)}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 