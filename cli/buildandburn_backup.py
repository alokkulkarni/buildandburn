#!/usr/bin/env python3
"""
BuildAndBurn - Infrastructure Provisioning and Deployment Tool

This script automates the provisioning of cloud infrastructure using Terraform 
and deployment of applications to Kubernetes. It follows a "build and burn" 
approach where environments can be quickly created and destroyed.

Main features:
- Creates AWS infrastructure (VPC, EKS, RDS, MQ, Redis, Kafka)
- Deploys applications to Kubernetes
- Provides environment management with unique IDs
- Handles dependencies between services
- Supports custom configurations via manifest files

Usage:
  python buildandburn.py up -m manifest.yaml    # Create/update infrastructure and deploy services
  python buildandburn.py down -i ENV_ID         # Destroy infrastructure for environment
  python buildandburn.py info -i ENV_ID         # Get information about environment
  python buildandburn.py list                    # List all environments

Author: BuildAndBurn Team
Version: 1.0.0
"""

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
import signal
import socket
import base64
import ipaddress
from urllib.parse import urlparse
import hashlib
import logging

# Version information
__version__ = "1.0.0"

# Constants
TERRAFORM_MIN_VERSION = "1.0.0"
KUBECTL_MIN_VERSION = "1.20.0"
AWS_CLI_MIN_VERSION = "2.0.0"

# Configuration settings
CONFIG = {
    "TERRAFORM_APPLY_TIMEOUT": 3600,  # 1 hour
    "PROGRESS_UPDATE_INTERVAL": 60,   # 1 minute
}

#####################################################################
# Logging and Output Functions
#####################################################################

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

def run_command(cmd, cwd=None, capture_output=False, allow_fail=False, env=None):
    """
    Execute a shell command with improved error handling and output capture.
    
    Args:
        cmd (str or list): Command to run (string or list of arguments)
        cwd (str, optional): Working directory for the command
        capture_output (bool): Whether to capture and return command output
        allow_fail (bool): If True, don't raise exception on command failure
        env (dict, optional): Environment variables for the command
        
    Returns:
        If capture_output is True, returns subprocess.CompletedProcess object
        Otherwise returns True if command succeeded
        
    Raises:
        Exception: If command fails and allow_fail is False
    """
    # Create a merged environment with existing env vars plus any provided ones
    merged_env = None
    if env:
        merged_env = os.environ.copy()
        merged_env.update(env)
    
    print_info(f"Executing command: {cmd}")
    if cwd:
        print_info(f"Working directory: {cwd}")
    
    try:
        if capture_output:
            if isinstance(cmd, list):
                result = subprocess.run(cmd, cwd=cwd, check=not allow_fail, 
                                      capture_output=True, text=True, env=merged_env)
                return result
            else:
                result = subprocess.run(cmd, cwd=cwd, check=not allow_fail, 
                                      capture_output=True, text=True, shell=True, env=merged_env)
                return result
        else:
            if isinstance(cmd, list):
                subprocess.run(cmd, cwd=cwd, check=not allow_fail, env=merged_env)
            else:
                subprocess.run(cmd, cwd=cwd, check=not allow_fail, shell=True, env=merged_env)
            return True
    except subprocess.CalledProcessError as e:
        if allow_fail:
            class ErrorResult:
                def __init__(self, exception):
                    self.returncode = exception.returncode
                    self.stdout = exception.stdout if hasattr(exception, 'stdout') else ""
                    self.stderr = exception.stderr if hasattr(exception, 'stderr') else ""
                    self.exception = exception
            
            return ErrorResult(e)
        else:
            print_error(f"Command failed with exit code {e.returncode}")
            if hasattr(e, 'stdout') and e.stdout:
                print_info("Command output:")
                print(e.stdout)
            if hasattr(e, 'stderr') and e.stderr:
                print_error("Command error output:")
                print(e.stderr)
            raise Exception(f"Command '{cmd}' returned non-zero exit status {e.returncode}.")
    except Exception as e:
        print_error(f"Exception running command: {str(e)}")
        traceback.print_exc()
        if allow_fail:
            class ErrorResult:
                def __init__(self, exception):
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = str(exception)
                    self.exception = exception
            
            return ErrorResult(e)
        else:
            raise Exception(f"Exception running command: {str(e)}")

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
        
def load_manifest(manifest_path):
    """
    Load and parse a YAML manifest file.
    
    Args:
        manifest_path (str): Path to the manifest file
        
    Returns:
        dict: Parsed manifest as a dictionary, or None if loading fails
    """
    try:
        with open(manifest_path, 'r') as file:
            manifest = yaml.safe_load(file)
        print_info("Manifest loaded successfully:")
        print(yaml.dump(manifest, default_flow_style=False, sort_keys=False))
        return manifest
    except Exception as e:
        print_error(f"Failed to load manifest: {str(e)}")
        return None

def generate_env_id():
    """
    Generate a unique environment ID to identify this deployment.
    
    Returns:
        str: 8-character hexadecimal environment ID
    """
    return uuid.uuid4().hex[:8]

def prepare_terraform_vars(manifest, env_id, project_dir):
    """
    Prepare Terraform variables based on the manifest configuration.
    
    This function extracts values from the manifest and transforms them into a format
    suitable for Terraform variable files. It handles specific configurations for
    different types of infrastructure components (EKS, RDS, MQ, Redis, Kafka).
    
    Args:
        manifest (dict): The parsed manifest containing configuration
        env_id (str): Unique environment ID for this deployment
        project_dir (str): Path to project directory
        
    Returns:
        dict: Dictionary of Terraform variables
    """
    # Initialize with common variables
    tf_vars = {
        "project_name": manifest['name'],
        "env_id": env_id,
        "region": manifest.get('region', 'us-west-2'),
        "dependencies": [],
    }
    
    # Add default VPC and EKS configuration if not specified
    tf_vars.update({
        "vpc_cidr": manifest.get('vpc_cidr', '10.0.0.0/16'),
        "eks_instance_types": manifest.get('eks_instance_types', ['t3.medium']),
        "eks_node_min": manifest.get('eks_node_min', 1),
        "eks_node_max": manifest.get('eks_node_max', 3),
        "k8s_version": manifest.get('k8s_version', '1.27'),
    })
    
    # Process dependencies
    dependencies = []
    if 'dependencies' in manifest and manifest['dependencies']:
        for dep in manifest['dependencies']:
            if 'type' in dep:
                dependencies.append(dep['type'])
    
    tf_vars["dependencies"] = dependencies
    
    # Determine if ingress should be enabled based on manifest
    # Check if ingress is explicitly defined in the manifest or if any service has ingress enabled
    enable_ingress = False
    
    # Check if ingress is defined at the manifest level
    if 'ingress' in manifest and manifest['ingress'].get('enabled', True):
        enable_ingress = True
    
    # Check if any services have ingress enabled
    if 'services' in manifest:
        for service in manifest.get('services', []):
            if service.get('ingress', {}).get('enabled', False):
                enable_ingress = True
                break
    
    # If not explicitly defined, enable ingress by default for better user experience
    if not 'ingress' in manifest:
        enable_ingress = True
    
    tf_vars["enable_ingress"] = enable_ingress
    
    # Add database-specific variables if needed
    if 'database' in dependencies:
        db_config = next((d for d in manifest['dependencies'] if d['type'] == 'database'), None)
        if db_config:
            tf_vars.update({
                "db_engine": db_config.get('engine', 'postgres'),
                "db_engine_version": db_config.get('version', '15'),
                "db_instance_class": db_config.get('instance_class', 'db.t3.micro'),
                "db_allocated_storage": int(db_config.get('allocated_storage', 20)),
            })
        else:
            print_warning("Database dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "db_engine": "postgres",
                "db_engine_version": "15",
                "db_instance_class": "db.t3.micro",
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
                "mq_auto_minor_version_upgrade": mq_config.get('auto_minor_version_upgrade', True),
            })
        else:
            print_warning("Queue dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "mq_engine_type": "RabbitMQ",
                "mq_engine_version": "3.13",
                "mq_instance_type": "mq.t3.micro",
                "mq_auto_minor_version_upgrade": True,
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
    
    # Add Kafka-specific variables if needed
    if 'kafka' in dependencies:
        kafka_config = next((d for d in manifest['dependencies'] if d['type'] == 'kafka'), None)
        if kafka_config:
            tf_vars.update({
                "kafka_version": kafka_config.get('version', '3.4.0'),
                "kafka_instance_type": kafka_config.get('instance_type', 'kafka.t3.small'),
                "kafka_broker_count": int(kafka_config.get('broker_count', 2)),
                "kafka_volume_size": int(kafka_config.get('volume_size', 100)),
                "kafka_monitoring_level": kafka_config.get('monitoring_level', 'DEFAULT'),
            })
        else:
            print_warning("Kafka dependency specified but no configuration found. Using defaults.")
            tf_vars.update({
                "kafka_version": "3.4.0",
                "kafka_instance_type": "kafka.t3.small",
                "kafka_broker_count": 2,
                "kafka_volume_size": 100,
                "kafka_monitoring_level": "DEFAULT",
            })
    
    return tf_vars

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

def setup_cleanup_handler(project_dir, terraform_project_dir):
    """
    Set up signal handlers to ensure proper cleanup on program interruption.
    
    This function creates handlers for SIGINT (Ctrl+C) and SIGTERM to ensure that
    any temporary resources are properly cleaned up when the program is interrupted.
    
    Args:
        project_dir (str): Path to project directory
        terraform_project_dir (str): Path to Terraform project directory
        
    Returns:
        function: The cleanup handler function
    """
    def cleanup_handler(signum=None, frame=None):
        """
        Clean up resources when the program is interrupted.
        
        Args:
            signum: Signal number (if called as signal handler)
            frame: Current stack frame (if called as signal handler)
        """
        print_info("\n" + "=" * 80)
        print_info("CLEANING UP RESOURCES")
        print_info("=" * 80)
        
        try:
            # Check if terraform has created any resources that need cleanup
            terraform_state = os.path.join(terraform_project_dir, "terraform.tfstate")
            if os.path.exists(terraform_state):
                print_warning("Terraform state found. You might need to run 'terraform destroy' to clean up resources.")
                print_info(f"State file: {terraform_state}")
            
            # Remove temporary files if they exist
            temp_dirs = [
                os.path.join(project_dir, "tmp"),
            ]
            
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    print_info(f"Removing temporary directory: {temp_dir}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            print_info("Cleanup completed.")
        except Exception as e:
            print_error(f"Error during cleanup: {str(e)}")
        
        print_info("Exiting...")
        sys.exit(0 if signum is None else signum)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_handler)  # Termination signal
    
    return cleanup_handler

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

def create_valid_state_file(state_file_path, terraform_dir=None):
    """
    Create a properly formatted empty state file.
    
    This function creates a valid empty Terraform state file with proper structure.
    
    Args:
        state_file_path (str): Path where the state file should be created
        terraform_dir (str, optional): Path to Terraform directory
        
    Returns:
        bool: True if state file was created successfully
    """
    try:
        # Make sure parent directory exists
        os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
        
        # Create a minimal valid state file
        empty_state = {
            "version": 4,
            "terraform_version": "1.0.0",
            "serial": 1,
            "lineage": str(uuid.uuid4()),
            "outputs": {},
            "resources": []
        }
        
        with open(state_file_path, 'w') as f:
            json.dump(empty_state, f, indent=2)
        
        print_success(f"Created properly formatted state file at: {state_file_path}")
        return True
    except Exception as e:
        print_error(f"Failed to create state file: {str(e)}")
        return False

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

def generate_resource_summary(manifest, tf_vars, terraform_project_dir):
    """
    Generate a summary of resources that will be created and their estimated costs.
    
    This function analyzes the Terraform configuration and manifest to provide
    a summary of AWS resources that will be provisioned and their approximate costs.
    
    Args:
        manifest (dict): The parsed manifest containing configuration
        tf_vars (dict): Terraform variables prepared from the manifest
        terraform_project_dir (str): Path to Terraform project directory
        
    Returns:
        tuple: (list of resources, float of total hourly cost)
    """
    # Initialize resource list and cost
    resources = []
    total_cost_per_hour = 0.0
    
    # Helper function to add a resource to the summary
    def add_resource(type_name, name, count, cost_per_hour):
        nonlocal total_cost_per_hour
    resources.append({
            "type": type_name,
            "name": name,
            "count": count,
            "cost_per_hour": cost_per_hour
        })
        total_cost_per_hour += cost_per_hour * count
    
    # EKS Cluster - always included
    add_resource(
        "EKS Cluster", 
        f"{tf_vars['project_name']}-{tf_vars['env_id']}", 
        1, 
        0.10  # Approximate cost per hour for EKS control plane
    )
    
    # EKS Nodes based on configuration
    instance_type = tf_vars['eks_instance_types'][0]
    node_count = tf_vars['eks_node_min']
    
    # Approximate cost mapping for common instance types
    instance_costs = {
        "t3.small": 0.02,
        "t3.medium": 0.04,
        "t3.large": 0.08,
        "m5.large": 0.10,
        "m5.xlarge": 0.20,
        "c5.large": 0.09,
        "c5.xlarge": 0.18,
        "r5.large": 0.13,
        "r5.xlarge": 0.26
    }
    
    instance_cost = instance_costs.get(instance_type, 0.04)  # Default to t3.medium cost
    add_resource(
        "EC2 Instance",
        f"eks-node-{instance_type}",
        node_count,
        instance_cost
    )
    
    # Add database if included
    if 'database' in tf_vars.get('dependencies', []):
        db_instance_class = tf_vars.get('db_instance_class', 'db.t3.micro')
        db_storage = tf_vars.get('db_allocated_storage', 20)
        
        # Approximate cost mapping for common RDS instance classes
        db_costs = {
            "db.t3.micro": 0.02,
            "db.t3.small": 0.04,
            "db.t3.medium": 0.08,
            "db.m5.large": 0.15,
            "db.m5.xlarge": 0.30
        }
        
        db_cost = db_costs.get(db_instance_class, 0.02)  # Default to micro cost
        storage_cost = 0.115 * db_storage / 30 / 24  # Approximate cost per GB per hour
        
        add_resource(
            "RDS Database",
            f"{tf_vars['project_name']}-{tf_vars['env_id']}-db",
            1,
            db_cost + storage_cost
        )
    
    # Add MQ broker if included
    if 'queue' in tf_vars.get('dependencies', []):
        mq_instance_type = tf_vars.get('mq_instance_type', 'mq.t3.micro')
        
        # Approximate cost mapping for common MQ instance types
        mq_costs = {
            "mq.t3.micro": 0.04,
            "mq.t3.small": 0.08,
            "mq.m5.large": 0.25
        }
        
        mq_cost = mq_costs.get(mq_instance_type, 0.04)  # Default to micro cost
        
        add_resource(
            "MQ Broker",
            f"{tf_vars['project_name']}-{tf_vars['env_id']}-mq",
            1,
            mq_cost
        )
    
    # Add ElastiCache if included
    if 'redis' in tf_vars.get('dependencies', []):
        redis_node_type = tf_vars.get('redis_node_type', 'cache.t3.micro')
        redis_cluster_size = tf_vars.get('redis_cluster_size', 1)
        
        # Approximate cost mapping for common ElastiCache node types
        redis_costs = {
            "cache.t3.micro": 0.02,
            "cache.t3.small": 0.04,
            "cache.t3.medium": 0.08,
            "cache.m5.large": 0.15
        }
        
        redis_cost = redis_costs.get(redis_node_type, 0.02)  # Default to micro cost
        
        add_resource(
            "ElastiCache Redis",
            f"{tf_vars['project_name']}-{tf_vars['env_id']}-redis",
            redis_cluster_size,
            redis_cost
        )
    
    # Add MSK if included
    if 'kafka' in tf_vars.get('dependencies', []):
        kafka_instance_type = tf_vars.get('kafka_instance_type', 'kafka.t3.small')
        kafka_broker_count = tf_vars.get('kafka_broker_count', 2)
        
        # Approximate cost mapping for common MSK instance types
        kafka_costs = {
            "kafka.t3.small": 0.06,
            "kafka.m5.large": 0.19,
            "kafka.m5.xlarge": 0.37
        }
        
        kafka_cost = kafka_costs.get(kafka_instance_type, 0.06)  # Default to small cost
        
        add_resource(
            "MSK Kafka",
            f"{tf_vars['project_name']}-{tf_vars['env_id']}-kafka",
            kafka_broker_count,
            kafka_cost
        )
    
    # Print the resource summary
    print_info("=" * 80)
    print_info("RESOURCE SUMMARY")
    print_info("=" * 80)
    
    # Format like a table
    print_info(f"{'Resource Type':<20} {'Name':<30} {'Count':<10} {'Est. Cost/Hour':<15}")
    print_info("-" * 75)
    
    for resource in resources:
        print_info(
            f"{resource['type']:<20} {resource['name']:<30} {resource['count']:<10} "
            f"${resource['cost_per_hour'] * resource['count']:.2f}/hr"
        )
    
    print_info("-" * 75)
    print_info(f"{'Total Estimated Cost':<50} ${total_cost_per_hour:.2f}/hr")
    print_info(f"{'Monthly Estimate (30 days)':<50} ${total_cost_per_hour * 24 * 30:.2f}")
    print_info("Cost estimates are approximate and may vary based on AWS pricing changes and actual usage.")
    print_info("Additional costs may be incurred for data transfer, storage, and other AWS services.")
    
    return resources, total_cost_per_hour

def provision_infrastructure(manifest, env_id, terraform_dir, args=None):
    """
    Provision infrastructure using Terraform based on the manifest configuration.
    
    This is the core function that handles the entire infrastructure provisioning process:
    1. Validates the manifest and ensures it contains required fields
    2. Creates a dedicated project directory for this environment
    3. Copies Terraform configuration files
    4. Runs pre-flight checks to verify AWS credentials and configuration
    5. Prepares Terraform variables based on the manifest
    6. Validates Terraform modules against manifest requirements
    7. Generates a resource summary with cost estimates
    8. Initializes Terraform and handles provider configurations
    9. Runs Terraform validation
    10. Executes Terraform plan and apply to create infrastructure
    11. Saves environment information for future reference
    
    The function implements sophisticated error handling, automatic recovery mechanisms,
    and detailed logging to handle various failure scenarios.
    
    Args:
        manifest (dict): The parsed manifest containing configuration
        env_id (str): Unique environment ID for this deployment
        terraform_dir (str): Path to base Terraform directory
        args (argparse.Namespace, optional): Command-line arguments
            - auto_approve: Skip confirmation prompts
            - skip_module_confirmation: Skip confirmation for module validation
            
    Returns:
        tuple: (project_dir, tf_output)
            - project_dir: Path to the project directory for this environment
            - tf_output: Dictionary of Terraform outputs
    """
    # Check if manifest is valid
    if manifest is None:
        print_error("Manifest is empty or invalid. Please provide a valid manifest file.")
        return None, {}
    
    if 'name' not in manifest:
        print_error("Manifest must contain a 'name' field. Please provide a valid manifest file.")
        return None, {}
    
    # Default auto_approve
    if args is None:
        class DefaultArgs:
            auto_approve = False
            skip_module_confirmation = False
            infrastructure_only = False
            no_deploy_k8s = False
        args = DefaultArgs()
        
    print_info("=" * 80)
    print_info("PROVISIONING INFRASTRUCTURE")
    print_info("=" * 80)
    print_info(f"Environment ID: {env_id}")
    print_info(f"Project name: {manifest['name']}")
    
    # Get region from manifest or use default
    region = manifest.get('region', 'us-west-2')
    print_info(f"Region: {region}")
    
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
        
        # Also check provider-aws.tf if it exists
        provider_aws_path = os.path.join(terraform_project_dir, "provider-aws.tf")
        if os.path.exists(provider_aws_path):
            with open(provider_aws_path, 'r') as f:
                provider_aws_content = f.read()
                if 'provider "aws"' in provider_aws_content:
                    print_info("AWS provider already defined in provider-aws.tf")
                    providers_already_defined = True
        
        # Check all .tf files for provider declarations
        tf_files = glob.glob(os.path.join(terraform_project_dir, "*.tf"))
        for tf_file in tf_files:
            if tf_file != os.path.join(terraform_project_dir, "providers.tf"):
                try:
                    with open(tf_file, 'r') as f:
                        content = f.read()
                        if 'provider "aws"' in content:
                            file_name = os.path.basename(tf_file)
                            print_info(f"AWS provider already defined in {file_name}")
                            providers_already_defined = True
                            break
                except Exception as e:
                    print_warning(f"Could not read {tf_file}: {str(e)}")
        
        # Also check for required_providers declaration
        required_providers_defined = False
        for tf_file in tf_files:
            try:
                with open(tf_file, 'r') as f:
                    content = f.read()
                    if 'required_providers' in content:
                        file_name = os.path.basename(tf_file)
                        print_info(f"required_providers already defined in {file_name}")
                        required_providers_defined = True
                        break
            except Exception as e:
                print_warning(f"Could not read {tf_file}: {str(e)}")
        
        # Remove providers.tf if it exists to avoid duplicate providers
        providers_file = os.path.join(terraform_project_dir, "providers.tf")
        if os.path.exists(providers_file):
            print_info("Removing existing providers.tf to avoid duplicates")
            os.remove(providers_file)
        
        # Only create providers.tf if providers and required_providers aren't already defined
        if not providers_already_defined and not required_providers_defined:
            print_info("Creating providers.tf file with provider and required_providers...")
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
        elif not providers_already_defined and required_providers_defined:
            print_info("Creating providers.tf file with only provider configuration...")
            with open(providers_file, 'w') as f:
                f.write(f"""
provider "aws" {{
  region = "{region}"
}}
""")
        elif providers_already_defined and not required_providers_defined:
            print_info("Creating providers.tf file with only required_providers configuration...")
            with open(providers_file, 'w') as f:
                f.write(f"""
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
        else:
            print_info("Skipping providers.tf creation as both provider and required_providers already exist")
        
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
        
        # Also check provider-aws.tf if it exists
        provider_aws_path = os.path.join(terraform_project_dir, "provider-aws.tf")
        if os.path.exists(provider_aws_path):
            with open(provider_aws_path, 'r') as f:
                provider_aws_content = f.read()
                if 'provider "aws"' in provider_aws_content:
                    print_info("AWS provider already defined in provider-aws.tf")
                    providers_already_defined = True
        
        # Check all .tf files for provider declarations
        tf_files = glob.glob(os.path.join(terraform_project_dir, "*.tf"))
        for tf_file in tf_files:
            if tf_file != os.path.join(terraform_project_dir, "providers.tf"):
                try:
                    with open(tf_file, 'r') as f:
                        content = f.read()
                        if 'provider "aws"' in content:
                            file_name = os.path.basename(tf_file)
                            print_info(f"AWS provider already defined in {file_name}")
                            providers_already_defined = True
                            break
                except Exception as e:
                    print_warning(f"Could not read {tf_file}: {str(e)}")
        
        # Also check for required_providers declaration
        required_providers_defined = False
        for tf_file in tf_files:
            try:
                with open(tf_file, 'r') as f:
                    content = f.read()
                    if 'required_providers' in content:
                        file_name = os.path.basename(tf_file)
                        print_info(f"required_providers already defined in {file_name}")
                        required_providers_defined = True
                        break
            except Exception as e:
                print_warning(f"Could not read {tf_file}: {str(e)}")
        
        # Remove providers.tf if it exists to avoid duplicate providers
        providers_file = os.path.join(terraform_project_dir, "providers.tf")
        if os.path.exists(providers_file):
            print_info("Removing existing providers.tf to avoid duplicates")
            os.remove(providers_file)
        
        # Only create providers.tf if providers and required_providers aren't already defined
        if not providers_already_defined and not required_providers_defined:
            print_info("Creating providers.tf file with provider and required_providers...")
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
        elif not providers_already_defined and required_providers_defined:
            print_info("Creating providers.tf file with only provider configuration...")
            with open(providers_file, 'w') as f:
                f.write(f"""
provider "aws" {{
  region = "{region}"
}}
""")
        elif providers_already_defined and not required_providers_defined:
            print_info("Creating providers.tf file with only required_providers configuration...")
            with open(providers_file, 'w') as f:
                f.write(f"""
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
        else:
            print_info("Skipping providers.tf creation as both provider and required_providers already exist")
        
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
        print_warning("Kubeconfig not found in Terraform outputs, attempting to get it from the EKS cluster")
        # Try to get the kubeconfig from the EKS cluster directly
        try:
            # Check if cluster_name is available in terraform output
            if 'cluster_name' in tf_output and 'value' in tf_output['cluster_name']:
                cluster_name = tf_output['cluster_name']['value']
                region = manifest.get('region', 'us-west-2')
                
                print_info(f"Getting kubeconfig for EKS cluster: {cluster_name} in region {region}")
                update_kubeconfig_cmd = ["aws", "eks", "update-kubeconfig", 
                                        "--name", cluster_name, 
                                        "--region", region]
                
                result = run_command(update_kubeconfig_cmd, capture_output=True)
                if result.returncode == 0:
                    print_success("Successfully obtained kubeconfig from EKS cluster")
                    # Get the kubeconfig from the default location
                    home = os.path.expanduser("~")
                    default_kubeconfig = os.path.join(home, ".kube", "config")
                    if os.path.exists(default_kubeconfig):
                        with open(default_kubeconfig, 'r') as kf:
                            kubeconfig = kf.read()
                        kubeconfig_path = os.path.join(project_dir, "kubeconfig")
                        print_info(f"Saving kubeconfig to: {kubeconfig_path}")
                        with open(kubeconfig_path, 'w') as f:
                            f.write(kubeconfig)
                    else:
                        print_error("Default kubeconfig not found after update")
                        return False
                else:
                    print_error(f"Failed to get kubeconfig for EKS cluster: {result.stderr}")
                    return False
            else:
                print_error("Cluster name not found in Terraform outputs")
                return False
        except Exception as e:
            print_error(f"Error getting kubeconfig from EKS cluster: {str(e)}")
            return False
    else:
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
    """
    Get access information for the deployed services.
    
    This function uses kubectl to get information about deployed services and ingresses
    in the Kubernetes cluster.
    
    Args:
        kubeconfig_path (str): Path to the kubeconfig file
        namespace (str): Kubernetes namespace to get resources from
        tf_output (dict): Terraform outputs
        
    Returns:
        dict: Dictionary with access information
    """
    # Initialize access info structure
    access_info = {
        "services": {},
        "ingresses": {},
        "resources": {}
    }
    
    # Check if the kubeconfig file exists
    if not os.path.exists(kubeconfig_path):
        print_warning(f"Kubeconfig not found at {kubeconfig_path}. Cannot retrieve access information.")
        return access_info
    
    # Set up environment for kubectl
        env = os.environ.copy()
        env["KUBECONFIG"] = kubeconfig_path
        
    # Create a log file for recording command outputs
    log_file = open(f"{os.path.dirname(kubeconfig_path)}/access_info.log", "w")
    log_file.write(f"Gathering access information for namespace: {namespace}\n")
    
    try:
        # Get services
        service_cmd = ["kubectl", "get", "service", "-n", namespace, "-o", "wide"]
        print_info(f"Running: {' '.join(service_cmd)}")
        log_file.write(f"Service command: {' '.join(service_cmd)}\n")
        
        service_process = subprocess.run(
            service_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if service_process.returncode == 0 and service_process.stdout.strip():
            log_file.write(f"Service output: {service_process.stdout}\n")
            print_info(f"Deployed services:\n{service_process.stdout}")
        else:
            print_info("No services deployed or found.")
            log_file.write("No services deployed or found.\n")
        
        # Get ingresses
        ingress_cmd = ["kubectl", "get", "ingress", "-n", namespace, "-o", "wide"]
        print_info(f"Running: {' '.join(ingress_cmd)}")
        log_file.write(f"Ingress command: {' '.join(ingress_cmd)}\n")
        
        ingress_process = subprocess.run(
            ingress_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if ingress_process.returncode == 0 and ingress_process.stdout.strip():
            log_file.write(f"Ingress output: {ingress_process.stdout}\n")
            print_info(f"Deployed ingresses:\n{ingress_process.stdout}")
        else:
            print_info("No ingresses deployed or found.")
            log_file.write("No ingresses deployed or found.\n")
        
        # Get service endpoints using JSON format
        service_result = run_command(
            ["kubectl", "get", "service", "-n", namespace, "-o", "json"],
            env=env,
            capture_output=True,
            allow_fail=True
        )
        
        # Get service information
        if hasattr(service_result, 'stdout') and service_result.returncode == 0:
            try:
                services = json.loads(service_result.stdout)
            
            # Service endpoints
            for svc in services.get("items", []):
                svc_name = svc["metadata"]["name"]
                svc_type = svc["spec"]["type"]
                
                    # Handle different service types
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
                            access_info["services"][svc_name] = f"LoadBalancer pending for {svc_name}"
                    elif svc_type == "NodePort":
                        if "nodePort" in svc["spec"]["ports"][0]:
                            node_port = svc["spec"]["ports"][0]["nodePort"]
                            access_info["services"][svc_name] = f"NodePort {node_port} (requires node IP)"
                    elif svc_type == "ClusterIP":
                        cluster_ip = svc["spec"]["clusterIP"]
                        access_info["services"][svc_name] = f"ClusterIP {cluster_ip} (internal only)"
            except json.JSONDecodeError:
                print_warning("Failed to parse service information as JSON")
                log_file.write("Failed to parse service information as JSON\n")
        
        # Get ingress endpoints using list format
        ingress_result = run_command(
            ["kubectl", "get", "ingress", "-n", namespace, "-o", "json"], 
            env=env,
            capture_output=True, 
            allow_fail=True
        )
        
        # Get ingress information
        if hasattr(ingress_result, 'stdout') and ingress_result.returncode == 0:
            try:
                ingresses = json.loads(ingress_result.stdout)
                
                # Ingress endpoints
                for ing in ingresses.get("items", []):
                    ing_name = ing["metadata"]["name"]
                    
                    # Try to get the host and status
                    if "status" in ing and "loadBalancer" in ing["status"] and "ingress" in ing["status"]["loadBalancer"]:
                        # Find hosts in the ingress spec
                        hosts = []
                        if "spec" in ing and "rules" in ing["spec"]:
                            for rule in ing["spec"]["rules"]:
                                if "host" in rule:
                                    hosts.append(rule["host"])
                        
                        # Get the load balancer addresses (could be hostnames or IPs)
                        lb_addresses = []
                        for lb in ing["status"]["loadBalancer"]["ingress"]:
                            if "hostname" in lb:
                                lb_addresses.append(lb["hostname"])
                            elif "ip" in lb:
                                lb_addresses.append(lb["ip"])
                        
                        # Determine the URL to show
                        if hosts and lb_addresses:
                            # If we have both hosts and lb addresses, use host for a nicer URL
                            host = hosts[0]
                                    access_info["ingresses"][ing_name] = f"http://{host}"
                        elif lb_addresses:
                            # Otherwise just use the LB address directly
                            access_info["ingresses"][ing_name] = f"http://{lb_addresses[0]}"
                        else:
                            access_info["ingresses"][ing_name] = f"Ingress address pending for {ing_name}"
                        else:
                            access_info["ingresses"][ing_name] = f"Ingress address pending for {ing_name}"
            except json.JSONDecodeError:
                print_warning("Failed to parse ingress information as JSON")
                log_file.write("Failed to parse ingress information as JSON\n")

        # Check terraform outputs for ingress controller information
        # This is used when the user doesn't deploy specific ingresses but can use the ingress controller directly
        if not access_info["ingresses"] and tf_output and "ingress_controller_hostname" in tf_output and tf_output["ingress_controller_hostname"]["value"]:
            ingress_hostname = tf_output["ingress_controller_hostname"]["value"]
            if ingress_hostname:
                access_info["ingresses"]["nginx-ingress-controller"] = f"http://{ingress_hostname}"
                print_info(f"Found NGINX Ingress Controller at: http://{ingress_hostname}")
                log_file.write(f"Found NGINX Ingress Controller at: http://{ingress_hostname}\n")
        elif not access_info["ingresses"] and tf_output and "ingress_controller_ip" in tf_output and tf_output["ingress_controller_ip"]["value"]:
            ingress_ip = tf_output["ingress_controller_ip"]["value"]
            if ingress_ip:
                access_info["ingresses"]["nginx-ingress-controller"] = f"http://{ingress_ip}"
                print_info(f"Found NGINX Ingress Controller at: http://{ingress_ip}")
                log_file.write(f"Found NGINX Ingress Controller at: http://{ingress_ip}\n")
    
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
                    
        # Add other resources too (Databases, Queues, etc.)
        if tf_output:
            # Database
            if "database_endpoint" in tf_output and tf_output["database_endpoint"]["value"]:
                access_info["resources"]["database"] = {
                    "endpoint": tf_output["database_endpoint"]["value"],
                    "username": tf_output["database_username"]["value"] if "database_username" in tf_output else None,
                    # Password is not included here for security reasons
                }
                
            # Message Queue
            if "mq_endpoint" in tf_output and tf_output["mq_endpoint"]["value"]:
                access_info["resources"]["queue"] = {
                    "endpoint": tf_output["mq_endpoint"]["value"],
                    "username": tf_output["mq_username"]["value"] if "mq_username" in tf_output else None,
                    # Password is not included here for security reasons
                }
                
            # Redis
            if "redis_primary_endpoint" in tf_output and tf_output["redis_primary_endpoint"]["value"]:
                access_info["resources"]["redis"] = {
                    "primary_endpoint": tf_output["redis_primary_endpoint"]["value"],
                    "reader_endpoint": tf_output["redis_reader_endpoint"]["value"] if "redis_reader_endpoint" in tf_output else None,
                    "port": tf_output["redis_port"]["value"] if "redis_port" in tf_output else 6379,
                }
                
            # Kafka
            if "kafka_bootstrap_brokers" in tf_output and tf_output["kafka_bootstrap_brokers"]["value"]:
                access_info["resources"]["kafka"] = {
                    "bootstrap_brokers": tf_output["kafka_bootstrap_brokers"]["value"],
                    "bootstrap_brokers_tls": tf_output["kafka_bootstrap_brokers_tls"]["value"] if "kafka_bootstrap_brokers_tls" in tf_output else None,
                }
    except Exception as e:
        print_error(f"Error getting access information: {str(e)}")
        log_file.write(f"Error getting access information: {str(e)}\n")
        traceback.print_exc(file=log_file)
    finally:
        log_file.close()
    
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

def fix_terraform_issues(terraform_project_dir, error_analysis, tf_vars_file, region):
    """
    Attempt to fix Terraform issues based on error analysis.
    
    Args:
        terraform_project_dir (str): Path to Terraform project directory
        error_analysis (dict): Analysis of errors from analyze_terraform_errors
        tf_vars_file (str): Path to the Terraform variables file
        region (str): AWS region
        
    Returns:
        bool: True if any fixes were applied, False otherwise
    """
    if not error_analysis["auto_fix_possible"]:
        print_info("No auto-fixable issues detected")
        return False
    
    fixed = False
    
    for action in error_analysis["fix_actions"]:
        if action == "add_provider_config":
            if add_provider_config(terraform_project_dir):
                fixed = True
        
        elif action == "reinit_upgrade":
            print_info("Attempting to reinitialize with upgrade...")
            try:
                run_command("terraform init -upgrade", cwd=terraform_project_dir)
                fixed = True
            except Exception as e:
                print_error(f"Reinitialize failed: {str(e)}")
        
        elif action == "check_required_vars":
            print_info("Checking for required variables...")
            try:
                # Get list of required variables
                result = run_command("terraform plan -detailed-exitcode", 
                                    cwd=terraform_project_dir,
                                    capture_output=True,
                                    allow_fail=True)
                if result.stderr and "No value for required variable" in result.stderr:
                    # Extract missing variable names
                    missing_vars = re.findall(r'No value for required variable "([^"]+)"', result.stderr)
                    
                    if missing_vars and tf_vars_file:
                        print_info(f"Adding missing variables to {tf_vars_file}: {', '.join(missing_vars)}")
                        with open(tf_vars_file, 'a') as f:
                            for var in missing_vars:
                                if var == "region" and region:
                                    f.write(f'\nregion = "{region}"\n')
            else:
                                    f.write(f'\n{var} = ""\n')
                        fixed = True
        except Exception as e:
                print_error(f"Variable check failed: {str(e)}")
        
        elif action == "fix_duplicate_providers":
            print_info("Attempting to fix duplicate provider definitions...")
            try:
                # Find all provider definitions
                provider_files = []
                for root, dirs, files in os.walk(terraform_project_dir):
                    for file in files:
                        if file.endswith(".tf"):
                            file_path = os.path.join(root, file)
                            with open(file_path, 'r') as f:
                                content = f.read()
                                if 'provider "aws"' in content:
                                    provider_files.append(file_path)
                
                if len(provider_files) > 1:
                    print_info(f"Found multiple provider definitions in: {', '.join(provider_files)}")
                    
                    # Keep the main provider definition and comment out others
                    main_provider = provider_files[0]
                    for provider_file in provider_files[1:]:
                        with open(provider_file, 'r') as f:
                            content = f.read()
                        
                        # Comment out the provider block
                        modified_content = re.sub(
                            r'(provider\s+"aws"\s+{[^}]*})', 
                            r'# Commented due to duplicate provider\n# \1', 
                            content
                        )
                        
                        with open(provider_file, 'w') as f:
                            f.write(modified_content)
                    
                    fixed = True
    except Exception as e:
                print_error(f"Provider fix failed: {str(e)}")
        
        elif action == "clear_plugin_cache":
            print_info("Clearing plugin cache...")
            try:
                # Remove .terraform directory
                shutil.rmtree(os.path.join(terraform_project_dir, ".terraform"), ignore_errors=True)
                # Remove lock file
                for f in glob.glob(os.path.join(terraform_project_dir, ".terraform.lock.hcl")):
                    os.remove(f)
                    
                # Reinitialize
                run_command("terraform init -reconfigure", cwd=terraform_project_dir)
                fixed = True
    except Exception as e:
                print_error(f"Cache clearing failed: {str(e)}")
    
    # Additional fix: For tags that are duplicated in default_tags
    if "tags are identical to those in the" in str(error_analysis):
        print_info("Attempting to fix duplicate tags issue...")
        try:
            # Identify problematic modules
            modules_dir = os.path.join(terraform_project_dir, "modules")
            for module_name in ["rds", "mq"]:
                module_path = os.path.join(modules_dir, module_name)
                if os.path.exists(module_path):
                    main_tf = os.path.join(module_path, "main.tf")
                    if os.path.exists(main_tf):
                        with open(main_tf, 'r') as f:
                            content = f.read()
                        
                        # Fix the secretsmanager resource tags
                        modified_content = re.sub(
                            r'(resource\s+"aws_secretsmanager_secret"\s+"[^"]+"\s+{[^}]*)\s+tags\s+=\s+var\.tags',
                            r'\1\n  tags = {}',
                            content
                        )
                        
                        if modified_content != content:
                            with open(main_tf, 'w') as f:
                                f.write(modified_content)
                            print_info(f"Fixed duplicate tags in {module_name} module")
                            fixed = True
        except Exception as e:
            print_error(f"Tags fix failed: {str(e)}")
    
    return fixed

def cmd_up(args):
    """
    Handle the 'up' command to create/update infrastructure and deploy services.
    
    This function orchestrates the entire build process:
    1. Loads the manifest file
    2. Generates a unique environment ID if not provided
    3. Provisions infrastructure using Terraform
    4. Deploys services to Kubernetes
    5. Displays access information for the deployed services
    
    Args:
        args (argparse.Namespace): Command-line arguments including:
            - manifest (str): Path to the manifest file
            - env_id (str, optional): Environment ID
            - auto_approve (bool): Skip confirmation prompts
            - no_generate_k8s (bool): Skip generating Kubernetes resources
            - dry_run (bool): Skip actual deployment
            - skip_module_confirmation (bool): Skip confirmation for module validation
            
    Returns:
        bool: True if successful, False otherwise
    """
    manifest_path = args.manifest
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENT CREATION")
    print_info("=" * 80)
    
    # Generate or use environment ID
    env_id = args.env_id if args.env_id else generate_env_id()
    print_info(f"Using environment ID: {env_id}")
    
    # Load manifest
    print_info(f"Loading manifest file: {manifest_path}")
    manifest = load_manifest(manifest_path)
    if not manifest:
        print_error("Failed to load manifest file")
                    return False
                
    # Get directory paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    terraform_dir = os.path.join(project_root, "terraform")
    k8s_dir = os.path.join(project_root, "k8s")
    
    print_info(f"Current directory: {current_dir}")
    print_info(f"Project root: {project_root}")
    print_info(f"Terraform directory: {terraform_dir}")
    print_info(f"Kubernetes directory: {k8s_dir}")
    
    # Run prerequisite checks
    if not check_prerequisites():
        print_error("Prerequisite check failed")
        return False
    
    # Provision infrastructure
    project_dir, tf_output = provision_infrastructure(manifest, env_id, terraform_dir, args=args)
    if not project_dir:
        print_error("Infrastructure provisioning failed")
                        return False
                    
    # Skip Kubernetes deployment if only infrastructure was requested
    if args.infrastructure_only:
        print_info("Infrastructure provisioning complete. Skipping Kubernetes deployment per --infrastructure-only flag.")
        get_access_info(os.path.join(project_dir, "kubeconfig"), f"bb-{manifest['name']}", tf_output)
        return True
    
    # Deploy to Kubernetes unless skipped
    if not args.no_deploy_k8s:
        if not deploy_to_kubernetes(manifest, tf_output, k8s_dir, project_dir):
            print_error("Kubernetes deployment failed")
            # Continue to show access info even if deployment failed partially
        
        # Get access information
        access_info = get_access_info(os.path.join(project_dir, "kubeconfig"), f"bb-{manifest['name']}", tf_output)
    else:
        print_info("Skipping Kubernetes deployment per --no-deploy-k8s flag")
        access_info = get_access_info(os.path.join(project_dir, "kubeconfig"), f"bb-{manifest['name']}", tf_output)
    
    print_success(f"🎉 Environment created successfully: {manifest['name']} ({env_id})")
    print_info(f"Environment directory: {project_dir}")
    
    # Display access information in a more user-friendly way
    kubeconfig_path = os.path.join(project_dir, "kubeconfig")
    namespace = f"bb-{manifest['name']}"
    
    print_info("=" * 80)
    print_info("ACCESS INFORMATION")
    print_info("=" * 80)
    
    if "primary_url" in access_info:
        print_success(f"PRIMARY APPLICATION URL: {access_info['primary_url']}")
                else:
        print_warning("No primary application URL available")
    
    # If there are LoadBalancer services, show them
    lb_services = False
    for svc_name, svc_url in access_info.get("services", {}).items():
        if not svc_url.startswith("Service:"):
            lb_services = True
            print_info(f"Service '{svc_name}' is available at: {svc_url}")
    
    if not lb_services:
        print_warning("No LoadBalancer services are available yet")
        print_info("The LoadBalancer may still be provisioning. Run the following to check service status:")
        print_info(f"  KUBECONFIG={kubeconfig_path} kubectl get svc -n {namespace}")
    
    # If there are ingresses, show them
    if access_info.get("ingresses", {}):
        for ing_name, ing_url in access_info["ingresses"].items():
            print_info(f"Ingress '{ing_name}' is available at: {ing_url}")
            print_info(f"Note: You may need to set up DNS for {ing_url.split('//')[1]} to work properly")
    
    # Show available commands for users
    print_info("=" * 80)
    print_info("USEFUL COMMANDS")
    print_info("=" * 80)
    print_info(f"Get service status:  KUBECONFIG={kubeconfig_path} kubectl get svc -n {namespace}")
    print_info(f"Get pod status:      KUBECONFIG={kubeconfig_path} kubectl get pods -n {namespace}")
    print_info(f"View application logs: KUBECONFIG={kubeconfig_path} kubectl logs -n {namespace} deployment/postgres-app")
    print_info(f"Port-forward to app: KUBECONFIG={kubeconfig_path} kubectl port-forward -n {namespace} svc/postgres-app 8080:80")
    print_info("Then access: http://localhost:8080")
    
    print_info("=" * 80)
    print_info("To destroy this environment later, run:")
    print_info(f"  python3 cli/buildandburn.py down -i {env_id} -a")
    print_info("=" * 80)
    
    return True

def cmd_down(args):
    """
    Handle the 'down' command to destroy infrastructure for an environment.
    
    This function handles the teardown process:
    1. Finds the environment directory based on the given ID
    2. Runs Terraform destroy to remove infrastructure
    3. Removes environment information
    
    Args:
        args (argparse.Namespace): Command-line arguments including:
            - env_id (str): Environment ID to destroy
            - auto_approve (bool): Skip confirmation prompts
            
    Returns:
        bool: True if successful, False otherwise
    """
    env_id = args.env_id
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENT DESTRUCTION")
    print_info("=" * 80)
    
    # Check if environment ID is provided
    if not env_id:
        print_error("Environment ID is required to destroy an environment")
        print_info("Use 'buildandburn list' to see available environments")
                        return False
                    
    # Find environment directory
    home_dir = os.path.expanduser("~")
    buildandburn_dir = os.path.join(home_dir, ".buildandburn")
    env_dir = os.path.join(buildandburn_dir, env_id)
    
    if not os.path.exists(env_dir):
        print_error(f"Environment directory not found: {env_dir}")
        print_info("Use 'buildandburn list' to see available environments")
        return False
    
    # Load environment info
    env_info_file = os.path.join(env_dir, "env_info.json")
    if not os.path.exists(env_info_file):
        print_error(f"Environment info file not found: {env_info_file}")
        if not args.force:
            print_info("Use --force to remove the directory anyway")
        return False
        else:
            print_warning(f"Forcibly removing directory: {env_dir}")
            shutil.rmtree(env_dir, ignore_errors=True)
            return True
    
    try:
        with open(env_info_file, 'r') as f:
            env_info = json.load(f)
        
        project_name = env_info.get('project_name', 'unknown')
        created_at = env_info.get('created_at', 'unknown')
        terraform_dir = env_info.get('terraform_dir')
        
        print_info(f"Environment: {project_name} ({env_id})")
        print_info(f"Created: {created_at}")
        
        if not terraform_dir or not os.path.exists(terraform_dir):
            print_error(f"Terraform directory not found: {terraform_dir}")
            if not args.force:
                print_info("Use --force to remove the directory anyway")
                return False
            else:
                print_warning(f"Forcibly removing directory: {env_dir}")
                shutil.rmtree(env_dir, ignore_errors=True)
        return True
        
        # Confirm destruction unless auto-approve is set
        if not args.auto_approve:
            confirm = input(f"Are you sure you want to destroy environment {project_name} ({env_id})? [y/N]: ")
            if confirm.lower() != 'y':
                print_info("Destruction cancelled")
        return False

        # Run Terraform destroy
    print_info("=" * 80)
        print_info("DESTROYING INFRASTRUCTURE")
    print_info("=" * 80)
    
        destroy_cmd = ["terraform", "destroy"]
        # Always add -auto-approve flag when running terraform destroy command
        # to prevent terraform from asking for confirmation again
        if args.auto_approve:
            destroy_cmd.append("-auto-approve")
        
        print_info(f"Running Terraform destroy in {terraform_dir}")
        try:
            # Use run_command directly which handles both auto-approve and non-auto-approve cases
            run_command(destroy_cmd, cwd=terraform_dir)
            print_success("Infrastructure destroyed successfully")
            except Exception as e:
            print_error(f"Error during Terraform destroy: {str(e)}")
            if not args.force:
                print_info("Use --force to remove the directory anyway")
                return False
            else:
                print_warning("Continuing with force removal despite Terraform error")
        
        # Remove environment directory
        print_info(f"Removing environment directory: {env_dir}")
        shutil.rmtree(env_dir, ignore_errors=True)
        
        print_success(f"Environment {project_name} ({env_id}) destroyed successfully")
    return True

    except Exception as e:
        print_error(f"Error destroying environment: {str(e)}")
        if args.force:
            print_warning(f"Forcibly removing directory: {env_dir}")
            shutil.rmtree(env_dir, ignore_errors=True)
            return True
        return False
        
def cmd_info(args):
    """
    Handle the 'info' command to display information about an environment.
    
    This function retrieves and displays detailed information about a specific
    environment, including configuration, resources, and access URLs.
    
    Args:
        args (argparse.Namespace): Command-line arguments including:
            - env_id (str): Environment ID to get information for (positional)
            - env_id_flag (str): Environment ID to get information for (flag-based)
            - detailed (bool): Display more detailed information
            
    Returns:
        bool: True if successful, False otherwise
    """
    # Get env_id from either positional argument or flag
    env_id = args.env_id if args.env_id else args.env_id_flag
    
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENT INFORMATION")
    print_info("=" * 80)
    
    # Check if environment ID is provided
    if not env_id:
        print_error("Environment ID is required to get information")
        print_info("Use 'buildandburn list' to see available environments")
        return False
    
    # Find environment directory
    home_dir = os.path.expanduser("~")
    buildandburn_dir = os.path.join(home_dir, ".buildandburn")
    env_dir = os.path.join(buildandburn_dir, env_id)
    
    if not os.path.exists(env_dir):
        print_error(f"Environment directory not found: {env_dir}")
        print_info("Use 'buildandburn list' to see available environments")
        return False

    # Load environment info
    env_info_file = os.path.join(env_dir, "env_info.json")
    if not os.path.exists(env_info_file):
        print_error(f"Environment info file not found: {env_info_file}")
        return False
    
    try:
        with open(env_info_file, 'r') as f:
            env_info = json.load(f)
        
        project_name = env_info.get('project_name', 'unknown')
        created_at = env_info.get('created_at', 'unknown')
        terraform_dir = env_info.get('terraform_dir')
        
        print_info(f"Environment: {project_name} ({env_id})")
        print_info(f"Created: {created_at}")
        print_info(f"Directory: {env_dir}")
        
        # Get Terraform output if available
        tf_output = {}
        if terraform_dir and os.path.exists(terraform_dir):
            try:
                tf_output_result = run_command(["terraform", "output", "-json"], 
                                             cwd=terraform_dir, capture_output=True, allow_fail=True)
                if tf_output_result.returncode == 0:
                    tf_output = json.loads(tf_output_result.stdout)
    except Exception as e:
                print_warning(f"Could not get Terraform output: {str(e)}")
        
        # Display access information
        if tf_output:
            print_info("=" * 80)
            print_info("ACCESS INFORMATION")
            print_info("=" * 80)
            
            # Try to get kubeconfig if available
            kubeconfig_path = os.path.join(env_dir, "kubeconfig")
            if os.path.exists(kubeconfig_path):
                namespace = f"bb-{project_name}"
                access_info = get_access_info(kubeconfig_path, namespace, tf_output)
                
                # Enhanced display of access information
                if "primary_url" in access_info:
                    print_success(f"PRIMARY APPLICATION URL: {access_info['primary_url']}")
                    else:
                    print_warning("No primary application URL available yet")
                
                # Check if LoadBalancer is still pending
                pending_lb = False
                for svc_name, svc_url in access_info.get("services", {}).items():
                    if "pending" in svc_url.lower():
                        pending_lb = True
                        print_warning(f"LoadBalancer for '{svc_name}' is still being provisioned")
                    elif not svc_url.startswith("Service:"):
                        print_info(f"Service '{svc_name}' is available at: {svc_url}")
                
                if pending_lb:
                    # Try to update loadbalancer status
                    try:
                        print_info("Checking for updates on LoadBalancer status...")
                        env = os.environ.copy()
                        env["KUBECONFIG"] = kubeconfig_path
                        result = run_command(["kubectl", "get", "svc", "-n", namespace], capture_output=True, env=env)
                        if result.returncode == 0:
                            print_info("Current service status:")
                            print_info(result.stdout)
    except Exception as e:
                        print_warning(f"Could not check LoadBalancer status: {str(e)}")
                
                # Display ingress information
                if access_info.get("ingresses", {}):
                    for ing_name, ing_url in access_info["ingresses"].items():
                        print_info(f"Ingress '{ing_name}' is available at: {ing_url}")
                
                # Show useful commands
                print_info("=" * 80)
                print_info("USEFUL COMMANDS")
                print_info("=" * 80)
                print_info(f"Get service status:  KUBECONFIG={kubeconfig_path} kubectl get svc -n {namespace}")
                print_info(f"Get pods status:     KUBECONFIG={kubeconfig_path} kubectl get pods -n {namespace}")
                print_info(f"Port-forward to app: KUBECONFIG={kubeconfig_path} kubectl port-forward -n {namespace} svc/postgres-app 8080:80")
                print_info("Then access: http://localhost:8080")
            else:
                print_warning("Kubeconfig not found. Infrastructure might not include Kubernetes.")
                # Try to fetch kubeconfig from EKS cluster
                if "eks_cluster_name" in tf_output and tf_output["eks_cluster_name"]["value"]:
                    print_info("Attempting to get kubeconfig from EKS cluster...")
                    try:
                        cluster_name = tf_output["eks_cluster_name"]["value"]
                        region = tf_output.get("region", {}).get("value", "eu-west-2")
                        update_cmd = ["aws", "eks", "update-kubeconfig", "--name", cluster_name, "--region", region]
                        result = run_command(update_cmd, capture_output=True)
        if result.returncode == 0:
                            print_success("Successfully obtained kubeconfig from EKS cluster")
                            print_info("Run the info command again to see access information")
            return True
    except Exception as e:
                        print_warning(f"Failed to get kubeconfig from EKS cluster: {str(e)}")
                
                print_info("To access the infrastructure, first get the kubeconfig from AWS EKS:")
                print_info("  aws eks update-kubeconfig --name <cluster-name> --region <region>")
                
                # Show raw Terraform outputs if detailed info requested
                if args.detailed:
                    print_info("=" * 80)
                    print_info("TERRAFORM OUTPUTS")
                    print_info("=" * 80)
                    
                    for output_name, output_value in tf_output.items():
                        if isinstance(output_value, dict) and 'value' in output_value:
                            # Handle complex output with sensitive values
                            if 'sensitive' in output_value and output_value['sensitive']:
                                print_info(f"{output_name}: [sensitive]")
                            elif isinstance(output_value['value'], (dict, list)):
                                print_info(f"{output_name}:")
                                print(json.dumps(output_value['value'], indent=2))
        else:
                                print_info(f"{output_name}: {output_value['value']}")
        
        # Show manifest information if available
        manifest_file = os.path.join(env_dir, "manifest.yaml")
        if os.path.exists(manifest_file) and args.detailed:
            try:
                with open(manifest_file, 'r') as f:
                    manifest = yaml.safe_load(f)
                
                print_info("=" * 80)
                print_info("MANIFEST")
                print_info("=" * 80)
                print(yaml.dump(manifest, default_flow_style=False, sort_keys=False))
            except Exception as e:
                print_warning(f"Could not load manifest: {str(e)}")
        
        return True
    
    except Exception as e:
        print_error(f"Error getting environment information: {str(e)}")
        return False

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

def cmd_list(args):
    """
    Handle the 'list' command to list all available environments.
    
    This function displays a table of all environments created with buildandburn,
    showing their project names, IDs, creation times, and regions.
    
    Args:
        args (argparse.Namespace): Command-line arguments
            
    Returns:
        bool: True if successful, False otherwise
    """
    print_info("=" * 80)
    print_info("BUILD AND BURN - ENVIRONMENTS")
    print_info("=" * 80)
    
    # Find environment directories
    home_dir = os.path.expanduser("~")
    buildandburn_dir = os.path.join(home_dir, ".buildandburn")
    
    if not os.path.exists(buildandburn_dir):
        print_info("No environments found")
        return True
    
    # Get all environment directories
    env_dirs = [d for d in os.listdir(buildandburn_dir) 
              if os.path.isdir(os.path.join(buildandburn_dir, d))]
    
    if not env_dirs:
        print_info("No environments found")
        return True
    
    # Collect environment information
    environments = []
    for env_id in env_dirs:
        env_dir = os.path.join(buildandburn_dir, env_id)
        env_info_file = os.path.join(env_dir, "env_info.json")
        
        if os.path.exists(env_info_file):
            try:
                with open(env_info_file, 'r') as f:
                    env_info = json.load(f)
                
                environments.append({
                    "project_name": env_info.get('project_name', 'unknown'),
                    "env_id": env_id,
                    "created_at": env_info.get('created_at', 'unknown'),
                    "region": env_info.get('region', 'unknown')
                })
            except Exception as e:
                print_warning(f"Could not load environment info for {env_id}: {str(e)}")
    
    if not environments:
        print_info("No environments found with valid info files")
        return True
    
    # Sort environments by creation time (newest first)
    environments.sort(key=lambda e: e["created_at"], reverse=True)
    
    # Display environments as a table
    print_info(f"{'Project':<30} {'ID':<10} {'Created':<25} {'Region':<15}")
    print_info("-" * 80)
    
    for env in environments:
        print_info(
            f"{env['project_name']:<30} {env['env_id']:<10} {env['created_at']:<25} {env['region']:<15}"
        )
    
    return True

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
    parser_up.add_argument('--infrastructure-only', action='store_true', help='Only provision infrastructure, skip Kubernetes deployment')
    parser_up.add_argument('--no-generate-k8s', action='store_true', help='Disable automatic generation of Kubernetes resources')
    parser_up.add_argument('--no-deploy-k8s', action='store_true', help='Skip deploying to Kubernetes after creating infrastructure')
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
    parser_info.add_argument('env_id', nargs='?', help='Environment ID to get information about')
    parser_info.add_argument('-i', '--env-id', dest='env_id_flag', help='Environment ID to get information about (alternative to positional argument)')
    parser_info.add_argument('-d', '--detailed', action='store_true', help='Display more detailed information')
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