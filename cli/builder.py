#!/usr/bin/env python3

import argparse
import os
import sys
import yaml
import json
import subprocess
import tempfile
import shutil
from pathlib import Path

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
        print_info(f"Running: {cmd}")
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
        return None

def check_tools():
    """Check if required tools are installed."""
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
    """Load the manifest YAML file."""
    try:
        with open(manifest_path, 'r') as f:
            manifest = yaml.safe_load(f)
            return manifest
    except Exception as e:
        print_error(f"Failed to load manifest: {e}")
        sys.exit(1)

def extract_terraform_vars(manifest, env_id):
    """Extract Terraform variables from the manifest."""
    # Extract dependencies
    dependencies = []
    if 'dependencies' in manifest:
        for dep in manifest['dependencies']:
            dependencies.append(dep['type'])
    
    tf_vars = {
        "project_name": manifest['name'],
        "env_id": env_id,
        "region": manifest.get('region', 'us-west-2'),
        "dependencies": dependencies,
    }
    
    # Database specific variables
    if 'database' in dependencies:
        db_config = next((d for d in manifest['dependencies'] if d['type'] == 'database'), None)
        if db_config:
            tf_vars.update({
                "db_engine": db_config.get('provider', 'postgres'),
                "db_engine_version": db_config.get('version', '13'),
                "db_instance_class": db_config.get('instance_class', 'db.t3.small'),
                "db_allocated_storage": int(db_config.get('storage', 20)),
            })
    
    # Queue specific variables
    if 'queue' in dependencies:
        mq_config = next((d for d in manifest['dependencies'] if d['type'] == 'queue'), None)
        if mq_config:
            tf_vars.update({
                "mq_engine_type": mq_config.get('provider', 'RabbitMQ'),
                "mq_engine_version": mq_config.get('version', '3.9.16'),
                "mq_instance_type": mq_config.get('instance_class', 'mq.t3.micro'),
            })
    
    return tf_vars

def apply_terraform(tf_vars, terraform_dir, working_dir):
    """Apply Terraform configuration with the given variables."""
    # Write variables to file
    tf_vars_file = os.path.join(working_dir, 'terraform.tfvars.json')
    with open(tf_vars_file, 'w') as f:
        json.dump(tf_vars, f, indent=2)
    
    # Initialize Terraform
    if not run_command("terraform init", cwd=terraform_dir):
        print_error("Failed to initialize Terraform")
        return None
    
    # Apply Terraform configuration
    if not run_command(f"terraform apply -auto-approve -var-file={tf_vars_file}", cwd=terraform_dir):
        print_error("Failed to apply Terraform configuration")
        return None
    
    # Get Terraform outputs
    tf_output_str = run_command("terraform output -json", cwd=terraform_dir)
    if not tf_output_str:
        print_error("Failed to get Terraform outputs")
        return None
    
    try:
        tf_output = json.loads(tf_output_str)
        # Convert outputs from {value, type, sensitive} format to just values
        tf_output_values = {}
        for key, output in tf_output.items():
            tf_output_values[key] = output.get("value")
        return tf_output_values
    except json.JSONDecodeError:
        print_error("Failed to parse Terraform outputs")
        return None

def generate_k8s_values(manifest, tf_output, k8s_dir, working_dir):
    """Generate Kubernetes values.yaml from manifest and Terraform outputs."""
    # Load base values template
    base_values_path = os.path.join(k8s_dir, "values.yaml")
    with open(base_values_path, 'r') as f:
        values = yaml.safe_load(f)
    
    # Update namespace
    values['namespace'] = f"bb-{manifest['name']}"
    
    # Process and update services
    service_configs = []
    for service in manifest.get('services', []):
        service_config = {
            'name': service['name'],
            'image': service['image'],
            'replicas': service.get('replicas', 1),
            'ports': [{
                'name': 'http',
                'containerPort': service.get('port', 8080)
            }],
            'service': {
                'type': 'ClusterIP',
                'ports': [{
                    'name': 'http',
                    'port': 80,
                    'targetPort': service.get('port', 8080)
                }]
            },
            'env': []
        }
        
        # Add environment variables for services based on dependencies
        if 'database' in tf_output:
            service_config['env'].extend([
                {
                    'name': 'DB_HOST',
                    'value': tf_output.get('database_endpoint', '').split(':')[0]
                },
                {
                    'name': 'DB_PORT',
                    'value': tf_output.get('database_endpoint', '').split(':')[1] if ':' in tf_output.get('database_endpoint', '') else '5432'
                },
                {
                    'name': 'DB_NAME',
                    'value': tf_output.get('db_name', manifest['name'])
                },
                {
                    'name': 'DB_USER',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': 'db-credentials',
                            'key': 'username'
                        }
                    }
                },
                {
                    'name': 'DB_PASSWORD',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': 'db-credentials',
                            'key': 'password'
                        }
                    }
                }
            ])
        
        if 'queue' in tf_output:
            service_config['env'].extend([
                {
                    'name': 'RABBITMQ_HOST',
                    'value': tf_output.get('mq_endpoint', '').split(':')[0]
                },
                {
                    'name': 'RABBITMQ_PORT',
                    'value': tf_output.get('mq_endpoint', '').split(':')[1] if ':' in tf_output.get('mq_endpoint', '') else '5672'
                },
                {
                    'name': 'RABBITMQ_USER',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': 'mq-credentials',
                            'key': 'username'
                        }
                    }
                },
                {
                    'name': 'RABBITMQ_PASSWORD',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': 'mq-credentials',
                            'key': 'password'
                        }
                    }
                }
            ])
        
        # Add default resource requirements
        service_config['resources'] = {
            'requests': {
                'cpu': '100m',
                'memory': '256Mi'
            },
            'limits': {
                'cpu': '500m',
                'memory': '512Mi'
            }
        }
        
        # Set up ingress if needed
        if service.get('expose', False):
            service_config['ingress'] = {
                'enabled': True,
                'className': 'nginx',
                'host': f"{service['name']}.{manifest['name']}.{tf_output.get('cluster_domain', 'example.com')}",
                'path': '/',
                'pathType': 'Prefix',
                'annotations': {
                    'nginx.ingress.kubernetes.io/rewrite-target': '/'
                }
            }
        
        service_configs.append(service_config)
    
    # Update the values with service configurations
    values['services'] = service_configs
    
    # Write the updated values file
    values_file = os.path.join(working_dir, 'values.yaml')
    with open(values_file, 'w') as f:
        yaml.dump(values, f, default_flow_style=False)
    
    return values_file

def deploy_to_kubernetes(values_file, tf_output, k8s_dir, manifest):
    """Deploy the application to Kubernetes using Helm."""
    if not tf_output or 'kubeconfig' not in tf_output:
        print_error("Missing Kubernetes configuration in Terraform output")
        return False
    
    # Save kubeconfig to a temporary file
    kubeconfig_path = os.path.join(os.path.expanduser("~"), ".kube", "buildandburn-config")
    os.makedirs(os.path.dirname(kubeconfig_path), exist_ok=True)
    with open(kubeconfig_path, 'w') as f:
        f.write(tf_output['kubeconfig'])
    
    # Set KUBECONFIG environment variable
    os.environ['KUBECONFIG'] = kubeconfig_path
    
    # Create namespace if it doesn't exist
    namespace = f"bb-{manifest['name']}"
    run_command(f"kubectl create namespace {namespace} --dry-run=client -o yaml | kubectl apply -f -")
    
    # Initialize Helm if needed
    run_command("helm repo update")
    
    # Install/upgrade chart for each service
    for service in manifest.get('services', []):
        service_name = service['name']
        print_info(f"Deploying {service_name}...")
        
        # Package the Helm chart
        chart_package = os.path.join(os.path.dirname(values_file), f"{service_name}.tgz")
        run_command(f"helm package {k8s_dir} -d {os.path.dirname(values_file)}")
        
        # Install/upgrade the Helm chart
        run_command(f"helm upgrade --install {service_name} {chart_package} "
                   f"--namespace {namespace} "
                   f"--values {values_file} "
                   f"--set name={service_name}")
    
    print_success("Deployment completed successfully!")
    return True

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Build and deploy environments based on manifest files')
    parser.add_argument('manifest', help='Path to the manifest YAML file')
    parser.add_argument('--env-id', help='Environment ID (defaults to a random value if not specified)')
    parser.add_argument('--terraform-dir', help='Path to the Terraform directory', default='terraform')
    parser.add_argument('--k8s-dir', help='Path to the Kubernetes directory', default='k8s')
    parser.add_argument('--output-dir', help='Directory to store generated files and state', default=None)
    
    args = parser.parse_args()
    
    # Check if required tools are installed
    check_tools()
    
    # Determine working directory
    if args.output_dir:
        working_dir = args.output_dir
        os.makedirs(working_dir, exist_ok=True)
    else:
        # Use a temporary directory
        working_dir = tempfile.mkdtemp(prefix="buildandburn-")
    
    print_info(f"Using working directory: {working_dir}")
    
    # Load the manifest
    manifest = load_manifest(args.manifest)
    
    # Use provided env_id or generate a new one
    env_id = args.env_id or manifest['name'].lower().replace(' ', '-') + '-' + os.urandom(4).hex()
    print_info(f"Environment ID: {env_id}")
    
    # Extract Terraform variables from manifest
    tf_vars = extract_terraform_vars(manifest, env_id)
    
    # Find absolute paths to terraform and k8s directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    terraform_dir = os.path.abspath(os.path.join(project_root, args.terraform_dir))
    k8s_dir = os.path.abspath(os.path.join(project_root, args.k8s_dir))
    
    # Apply Terraform to provision infrastructure
    print_info("Provisioning infrastructure with Terraform...")
    tf_output = apply_terraform(tf_vars, terraform_dir, working_dir)
    if not tf_output:
        print_error("Failed to provision infrastructure")
        sys.exit(1)
    
    # Generate Kubernetes values file
    print_info("Generating Kubernetes configuration...")
    values_file = generate_k8s_values(manifest, tf_output, k8s_dir, working_dir)
    
    # Deploy to Kubernetes
    print_info("Deploying to Kubernetes...")
    if not deploy_to_kubernetes(values_file, tf_output, k8s_dir, manifest):
        print_error("Failed to deploy to Kubernetes")
        sys.exit(1)
    
    # Print access information
    print_success(f"Environment deployed successfully with ID: {env_id}")
    print_info("Access information:")
    
    # Print access URLs for services with ingress
    for service in manifest.get('services', []):
        if service.get('expose', False):
            print_info(f"  {service['name']}: http://{service['name']}.{manifest['name']}.{tf_output.get('cluster_domain', 'example.com')}")
    
    # Print database connection info if available
    if 'database_endpoint' in tf_output:
        print_info(f"  Database: {tf_output['database_endpoint']}")
    
    # Print queue connection info if available
    if 'mq_endpoint' in tf_output:
        print_info(f"  Message Queue: {tf_output['mq_endpoint']}")
    
    print_info(f"Working directory with configuration: {working_dir}")

if __name__ == "__main__":
    main() 