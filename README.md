# Build and Burn

A tool for creating disposable development environments with Terraform and Kubernetes.

## Overview

Build and Burn is a command-line tool that allows you to:

1. Provision infrastructure using Terraform
2. Deploy applications to Kubernetes
3. Provide easy access to your applications
4. Destroy everything when you're done

## Features

- **Manifest-based Configuration**: Define your infrastructure and applications in a single YAML file
- **Infrastructure Provisioning**: Automated provisioning using Terraform
- **Application Deployment**: Deploy applications to Kubernetes
- **Automated Kubernetes Resource Generation**: Generate Kubernetes manifests or Helm charts from your application specifications
- **Custom Kubernetes Resources**: Use your own Helm charts or Kubernetes manifests
- **Dependency Management**: Automatically inject environment variables for service dependencies
- **Access URL Generation**: Get URLs to access your applications
- **Environment Management**: Easy creation and destruction of environments

## Installation

### From Repository

```bash
# Clone the repository
git clone https://github.com/username/buildandburn.git
cd buildandburn

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the CLI tool in development mode
pip install -e .
```

### Direct Installation

```bash
# Using pip
pip install buildandburn

# Or directly from GitHub
pip install git+https://github.com/username/buildandburn.git
```

## Usage

### Creating an Environment

```bash
# Create a new environment from a manifest file
buildandburn up --manifest examples/sample-manifest.yaml

# Create a new environment with a specific ID
buildandburn up --manifest examples/sample-manifest.yaml --env-id my-env-id

# Create a new environment with auto-approval for Terraform
buildandburn up --manifest examples/sample-manifest.yaml --auto-approve

# Create a new environment without automatically generating Kubernetes resources
buildandburn up --manifest examples/sample-manifest.yaml --no-generate-k8s
```

### Listing Environments

```bash
# List all environments
buildandburn list
```

### Getting Environment Information

```bash
# Get information about an environment
buildandburn info <env-id>
```

### Destroying an Environment

```bash
# Destroy an environment
buildandburn down <env-id>

# Destroy with force option (ignores errors)
buildandburn down <env-id> --force

# Destroy with auto-approval (skips confirmation)
buildandburn down <env-id> --auto-approve

# Keep local files after destroying infrastructure
buildandburn down <env-id> --keep-local
```

### Command Options

| Command | Option | Description |
|---------|--------|-------------|
| `up` | `--manifest`, `-m` | Path to manifest file (required) |
| `up` | `--env-id`, `-i` | Custom environment ID (auto-generated if not provided) |
| `up` | `--auto-approve`, `-a` | Skip Terraform confirmation prompts |
| `up` | `--no-generate-k8s` | Don't auto-generate Kubernetes resources |
| `down` | `--force`, `-f` | Force destruction even if errors occur |
| `down` | `--auto-approve`, `-a` | Skip Terraform destroy confirmation |
| `down` | `--keep-local`, `-k` | Keep local environment files after destroying resources |

## Manifest File

The manifest file defines both your infrastructure and applications. Here's an example:

```yaml
name: sample-app
description: "Sample application for Build and Burn"
region: eu-west-2

# Optional: Custom Kubernetes resources path
k8s_path: "./custom-k8s/test-app"

# Infrastructure configuration
infrastructure:
  provider: aws
  
  # Kubernetes cluster configuration
  kubernetes:
    version: "1.25"
    node_type: "t3.medium"
    node_count: 2
  
  # Optional: Database configuration
  database:
    enabled: true
    engine: postgres
    version: "14.6"

# Application services
services:
  - name: nginx
    image: "nginx:alpine"
    replicas: 1
    port: 80
    # Use LoadBalancer for public access
    service:
      type: LoadBalancer
      port: 80
    # Expose via Ingress
    ingress:
      enabled: true
      host: nginx.example.com
    # Sample content
    configMapData:
      index.html: |
        <!DOCTYPE html>
        <html>
        <head>
          <title>Build and Burn Test App</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              margin: 40px;
              text-align: center;
            }
          </style>
        </head>
        <body>
          <h1>Build and Burn Test App</h1>
          <p>This is a simple test application.</p>
        </body>
        </html>
```

For more complex examples, see the [examples directory](./examples).

## Using Custom Kubernetes Resources

Build and Burn allows you to use your own Kubernetes resources instead of auto-generating them. There are two main ways to do this:

### 1. Specify Custom Resources in Manifest

Add a `k8s_path` field to your manifest pointing to your custom resources:

```yaml
name: test-app
region: eu-west-2

# Custom k8s path
k8s_path: "./custom-k8s/test-app"

# Services to deploy
services:
  # ... service definitions ...
```

The `k8s_path` can point to:
- A directory containing a Helm chart (with Chart.yaml)
- A directory containing Kubernetes YAML manifests
- A single Kubernetes YAML file

### 2. Use Standard Locations

Without specifying `k8s_path`, Build and Burn will look for Kubernetes resources in these standard locations:
- `k8s/chart/` - For Helm charts
- `k8s/manifests/` - For Kubernetes manifests

### Sample Custom Helm Chart Structure

```
custom-k8s/test-app/
├── Chart.yaml              # Helm chart definition
├── values.yaml             # Values for the chart
└── templates/              # Template directory
    ├── _helpers.tpl        # Helper templates for labels
    ├── configmap.yaml      # ConfigMap for content
    ├── deployment.yaml     # Application deployment
    ├── service.yaml        # Service definition
    └── ingress.yaml        # Ingress for external access
```

### Important Notes on Custom Resources

1. **Namespace Handling**: When using Helm charts, comment out any namespace.yaml template to avoid ownership conflicts. Build and Burn will create the namespace before Helm deployment.

2. **Service Types**: Use `LoadBalancer` type services for public access or configure an Ingress controller properly.

3. **Values Substitution**: Build and Burn generates a values.yaml file from your manifest. Your custom templates should use these values.

## Kubernetes Resource Generation

Build and Burn includes a Kubernetes manifest generator. You can use it standalone or as part of the main tool.

### Standalone Usage

```bash
# Generate Kubernetes manifests from a manifest file
python cli/k8s_generator.py examples/sample-manifest.yaml -o k8s/generated

# Generate a Helm chart
python cli/k8s_generator.py examples/sample-manifest.yaml --helm -o k8s/generated

# Generate both manifests and a Helm chart
python cli/k8s_generator.py examples/sample-manifest.yaml --all -o k8s/generated

# Dry-run validation (doesn't create files)
python dry_validate.py examples/sample-manifest.yaml
```

### Integration with Build and Burn

When using the main `buildandburn` command, the tool follows this priority order:
1. Custom path specified in the manifest's `k8s_path` field
2. Existing Helm chart in the standard location (`k8s/chart`)
3. Existing Kubernetes manifests in the standard location (`k8s/manifests`)
4. Automatically generated resources (if not disabled with `--no-generate-k8s`)

## Making Applications Publicly Accessible

There are two main ways to make your applications publicly accessible:

### 1. LoadBalancer Service Type

In your manifest or custom Kubernetes resources, set the service type to LoadBalancer:

```yaml
services:
  - name: nginx
    image: nginx:alpine
    service:
      type: LoadBalancer  # Use this for public access
      port: 80
```

This will automatically provision a cloud load balancer with a public DNS name or IP address.

### 2. Ingress Resources

Configure Ingress resources with proper Ingress controller:

```yaml
services:
  - name: nginx
    image: nginx:alpine
    ingress:
      enabled: true
      host: my-app.example.com
      annotations:
        kubernetes.io/ingress.class: nginx
```

For this to work, you need to:
- Have an Ingress controller installed in your cluster
- Configure DNS records for the host

## Troubleshooting

### Helm Deployment Issues

If you encounter "invalid ownership metadata" errors during Helm deployment, it's usually due to namespace conflicts. Build and Burn now handles this automatically by:

1. Adding `--create-namespace` flag to Helm commands
2. Cleaning up conflicting namespaces and retrying when ownership issues are detected
3. Disabling namespace templates in generated Helm charts

### Service Access Issues

If your application isn't accessible:

1. Check the service type:
   ```bash
   kubectl get svc -n bb-<app-name>
   ```

2. For ClusterIP services (internal only), update to LoadBalancer:
   ```bash
   # Update your Helm chart values.yaml
   service:
     type: LoadBalancer
     port: 80
   
   # Then upgrade your release
   helm upgrade <release-name> /path/to/chart --namespace bb-<app-name>
   ```

3. For temporary access to ClusterIP services, use port forwarding:
   ```bash
   kubectl port-forward -n bb-<app-name> svc/<service-name> 8080:80
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 