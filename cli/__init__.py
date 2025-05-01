"""
Build and Burn CLI Tool

A tool for creating and managing disposable development and testing environments
using Terraform and Kubernetes.
"""

__version__ = "0.1.0"

from .buildandburn import (
    print_color, print_success, print_info, print_warning, print_error,
    run_command, check_prerequisites, load_manifest, generate_env_id,
    cmd_up, cmd_down, cmd_info, cmd_list
) 