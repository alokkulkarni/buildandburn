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
