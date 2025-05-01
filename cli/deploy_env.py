#!/usr/bin/env python3

import argparse
import os
import sys
import yaml
import json
import tempfile
import shutil
import subprocess
import time
from pathlib import Path

# Import functions from the main CLI tool
try:
    from buildandburn import (
        print_color, print_info, print_success, print_error, print_warning,
        run_command, check_prerequisites, load_manifest, generate_env_id
    )
except ImportError:
    # Define functions if buildandburn module is not available
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

    def run_command(cmd, cwd=None):
        """Run a shell command and return the output."""
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd,
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print_error(f"Command failed with exit code {e.returncode}")
            print_error(f"Error: {e.stderr.strip()}")
            sys.exit(1)

    def check_prerequisites():
        """Check if all the required tools are installed."""
        tools = {
            "terraform": "terraform --version",
            "kubectl": "kubectl version --client",
            "helm": "helm version --short",
            "aws": "aws --version"
        }
        
        missing = []
        for tool, cmd in tools.items():
            try:
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                missing.append(tool)
        
        if missing:
            print_error(f"Missing required tools: {', '.join(missing)}")
            print_info("Please install these tools and try again.")
            sys.exit(1)

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
        import uuid
        return str(uuid.uuid4())[:8]

def get_project_root():
    """Get the project root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

def create_k8s_template(manifest, tf_output, env_id, working_dir):
    """Create Kubernetes template based on manifest and Terraform output."""
    print_info("Creating Kubernetes template...")
    
    # Create values.yaml based on the manifest
    values = {
        "namespace": f"bb-{manifest['name']}",
        "ingress": {
            "domain": f"{manifest['name']}.local"
        },
        "services": []
    }
    
    # Add services from manifest
    for service in manifest.get('services', []):
        service_config = {
            "name": service['name'],
            "image": service['image'],
            "replicas": service.get('replicas', 1),
            "ports": [
                {
                    "name": "http",
                    "containerPort": service.get('port', 8080)
                }
            ],
            "service": {
                "type": "ClusterIP",
                "ports": [
                    {
                        "name": "http",
                        "port": 80,
                        "targetPort": service.get('port', 8080)
                    }
                ]
            },
            "env": []
        }
        
        # Add environment variables for database if needed
        if 'database_endpoint' in tf_output:
            db_host = tf_output['database_endpoint'].split(':')[0]
            db_port = tf_output['database_endpoint'].split(':')[1] if ':' in tf_output['database_endpoint'] else '5432'
            
            service_config['env'].extend([
                {
                    "name": "DB_HOST",
                    "value": db_host
                },
                {
                    "name": "DB_PORT",
                    "value": db_port
                },
                {
                    "name": "DB_NAME",
                    "value": manifest['name']
                },
                {
                    "name": "DB_USER",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "db-credentials",
                            "key": "username"
                        }
                    }
                },
                {
                    "name": "DB_PASSWORD",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "db-credentials",
                            "key": "password"
                        }
                    }
                }
            ])
        
        # Add environment variables for message queue if needed
        if 'mq_endpoint' in tf_output:
            mq_host = tf_output['mq_endpoint'].split(':')[0]
            mq_port = tf_output['mq_endpoint'].split(':')[1] if ':' in tf_output['mq_endpoint'] else '5672'
            
            service_config['env'].extend([
                {
                    "name": "RABBITMQ_HOST",
                    "value": mq_host
                },
                {
                    "name": "RABBITMQ_PORT",
                    "value": mq_port
                },
                {
                    "name": "RABBITMQ_USER",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "mq-credentials",
                            "key": "username"
                        }
                    }
                },
                {
                    "name": "RABBITMQ_PASSWORD",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "mq-credentials",
                            "key": "password"
                        }
                    }
                }
            ])
        
        # Add resource requirements
        service_config['resources'] = {
            "requests": {
                "cpu": "100m",
                "memory": "256Mi"
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi"
            }
        }
        
        # Add ingress configuration if needed
        if service.get('expose', True):  # Default to exposing services
            service_config['ingress'] = {
                "enabled": True,
                "className": "nginx",
                "host": f"{service['name']}.{manifest['name']}.local",
                "path": "/",
                "pathType": "Prefix",
                "annotations": {
                    "nginx.ingress.kubernetes.io/rewrite-target": "/"
                }
            }
        
        values['services'].append(service_config)
    
    # Write values file
    values_file = os.path.join(working_dir, 'values.yaml')
    with open(values_file, 'w') as f:
        yaml.dump(values, f, default_flow_style=False)
    
    print_success(f"Kubernetes values file created: {values_file}")
    return values_file

def deploy_to_kubernetes(values_file, kubeconfig, env_id, working_dir):
    """Deploy the application to Kubernetes using Helm."""
    print_info("Deploying to Kubernetes...")
    
    # Save kubeconfig to a temporary file
    kubeconfig_path = os.path.join(working_dir, 'kubeconfig.yaml')
    with open(kubeconfig_path, 'w') as f:
        f.write(kubeconfig)
    
    # Set KUBECONFIG environment variable
    os.environ['KUBECONFIG'] = kubeconfig_path
    
    # Get Kubernetes values
    with open(values_file, 'r') as f:
        values = yaml.safe_load(f)
    
    # Create namespace
    namespace = values['namespace']
    run_command(f"kubectl create namespace {namespace} --dry-run=client -o yaml | kubectl apply -f -")
    
    # Copy the Helm chart to the working directory
    project_root = get_project_root()
    k8s_dir = os.path.join(project_root, 'k8s')
    working_chart_dir = os.path.join(working_dir, 'chart')
    os.makedirs(working_chart_dir, exist_ok=True)
    
    # Copy chart files
    for item in os.listdir(k8s_dir):
        item_path = os.path.join(k8s_dir, item)
        if os.path.isfile(item_path):
            shutil.copy(item_path, os.path.join(working_chart_dir, item))
        elif os.path.isdir(item_path) and item == 'templates':
            shutil.copytree(item_path, os.path.join(working_chart_dir, 'templates'), dirs_exist_ok=True)
    
    # Package the Helm chart
    run_command(f"helm package {working_chart_dir} -d {working_dir}")
    chart_package = os.path.join(working_dir, 'buildandburn-0.1.0.tgz')
    
    # Deploy each service
    for service in values.get('services', []):
        service_name = service['name']
        print_info(f"Deploying {service_name}...")
        
        # Create a temporary values file specific to this service
        service_values = values.copy()
        service_values['name'] = service_name
        
        service_values_file = os.path.join(working_dir, f'{service_name}-values.yaml')
        with open(service_values_file, 'w') as f:
            yaml.dump(service_values, f, default_flow_style=False)
        
        # Deploy with Helm
        run_command(f"helm upgrade --install {service_name} {chart_package} "
                   f"--namespace {namespace} "
                   f"--values {service_values_file}")
    
    print_success("Deployment to Kubernetes completed successfully!")
    
    # Print access information
    print_info("\nAccess Information:")
    for service in values.get('services', []):
        service_name = service['name']
        if 'ingress' in service and service['ingress'].get('enabled', False):
            host = service['ingress'].get('host', f"{service_name}.{values['namespace']}.local")
            print_info(f"  {service_name}: http://{host}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Deploy a Build and Burn environment from a manifest file')
    parser.add_argument('manifest', help='Path to the manifest YAML file')
    parser.add_argument('--env-id', help='Environment ID (defaults to a random ID if not specified)')
    parser.add_argument('--output-dir', help='Directory to output temporary files', default=None)
    args = parser.parse_args()
    
    # Check prerequisites
    check_prerequisites()
    
    # Load manifest
    manifest = load_manifest(args.manifest)
    
    # Generate or use provided environment ID
    env_id = args.env_id or generate_env_id()
    print_info(f"Using environment ID: {env_id}")
    
    # Create working directory
    if args.output_dir:
        working_dir = args.output_dir
        os.makedirs(working_dir, exist_ok=True)
    else:
        working_dir = tempfile.mkdtemp(prefix=f"buildandburn-{env_id}-")
    
    print_info(f"Using working directory: {working_dir}")
    
    # Create the infrastructure using the main CLI tool
    print_info("Provisioning infrastructure...")
    try:
        from buildandburn import cmd_up
        # Mock args object for cmd_up
        class Args:
            def __init__(self):
                self.manifest = args.manifest
                self.env_id = env_id
                self.keep_local = True
        
        # Call the cmd_up function from buildandburn
        tf_output, project_dir = cmd_up(Args())
    except (ImportError, AttributeError):
        # If we can't import from buildandburn, use the terraform directory directly
        print_warning("Could not import from buildandburn module. Using terraform directory directly.")
        project_root = get_project_root()
        terraform_dir = os.path.join(project_root, 'terraform')
        
        # Run terraform init and apply
        print_info("Initializing Terraform...")
        run_command("terraform init", cwd=terraform_dir)
        
        # Create tfvars file
        tfvars = {
            "project_name": manifest['name'],
            "env_id": env_id,
            "region": manifest.get('region', 'us-west-2'),
            "dependencies": [dep['type'] for dep in manifest.get('dependencies', [])]
        }
        
        # Add database specific variables if needed
        if any(dep['type'] == 'database' for dep in manifest.get('dependencies', [])):
            db_config = next((dep for dep in manifest.get('dependencies', []) if dep['type'] == 'database'), {})
            tfvars.update({
                "db_engine": db_config.get('provider', 'postgres'),
                "db_engine_version": db_config.get('version', '13'),
                "db_instance_class": db_config.get('instance_class', 'db.t3.small'),
                "db_allocated_storage": int(db_config.get('storage', 20)),
            })
        
        # Add queue specific variables if needed
        if any(dep['type'] == 'queue' for dep in manifest.get('dependencies', [])):
            mq_config = next((dep for dep in manifest.get('dependencies', []) if dep['type'] == 'queue'), {})
            tfvars.update({
                "mq_engine_type": mq_config.get('provider', 'RabbitMQ'),
                "mq_engine_version": mq_config.get('version', '3.9.16'),
                "mq_instance_type": mq_config.get('instance_class', 'mq.t3.micro'),
            })
        
        # Write tfvars file
        tfvars_file = os.path.join(working_dir, 'terraform.tfvars.json')
        with open(tfvars_file, 'w') as f:
            json.dump(tfvars, f, indent=2)
        
        # Apply terraform configuration
        print_info("Applying Terraform configuration...")
        run_command(f"terraform apply -auto-approve -var-file={tfvars_file}", cwd=terraform_dir)
        
        # Get terraform outputs
        tf_output_str = run_command("terraform output -json", cwd=terraform_dir)
        tf_output = json.loads(tf_output_str)
        
        # Convert output from {value, type} format to just value
        tf_output_values = {}
        for key, output in tf_output.items():
            if isinstance(output, dict) and 'value' in output:
                tf_output_values[key] = output['value']
            else:
                tf_output_values[key] = output
        
        tf_output = tf_output_values
        project_dir = working_dir
    
    # Create Kubernetes template
    values_file = create_k8s_template(manifest, tf_output, env_id, working_dir)
    
    # Get kubeconfig from Terraform output
    kubeconfig = tf_output.get('kubeconfig')
    if not kubeconfig:
        print_error("No kubeconfig found in Terraform output. Cannot deploy to Kubernetes.")
        sys.exit(1)
    
    # Deploy to Kubernetes
    deploy_to_kubernetes(values_file, kubeconfig, env_id, working_dir)
    
    print_success(f"\nEnvironment deployed successfully with ID: {env_id}")
    print_info(f"Working directory: {working_dir}")
    print_info(f"Project directory: {project_dir}")
    
    # Save environment info
    env_info = {
        "env_id": env_id,
        "project_name": manifest['name'],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": manifest,
        "terraform_output": tf_output,
        "working_dir": working_dir,
        "project_dir": project_dir
    }
    
    # Save environment information
    env_info_file = os.path.join(working_dir, 'env_info.json')
    with open(env_info_file, 'w') as f:
        json.dump(env_info, f, indent=2)
    
    print_info(f"Environment information saved to: {env_info_file}")

if __name__ == "__main__":
    main() 