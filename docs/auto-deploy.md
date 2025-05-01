# Automatic Kubernetes Deployment

The Build and Burn solution provides functionality to automatically generate Kubernetes configurations from a manifest file and deploy them to the provisioned infrastructure.

## Prerequisites

- Python 3.7 or higher
- Terraform 1.0 or higher
- Kubectl
- Helm
- AWS CLI (configured with appropriate credentials)

## Using the Auto-Deploy Functionality

The `deploy_env.py` script handles the complete process of:

1. Provisioning AWS infrastructure using Terraform
2. Generating Kubernetes configuration based on the manifest
3. Deploying services to the created Kubernetes cluster

### Basic Usage

```bash
./cli/deploy_env.py path/to/manifest.yaml
```

This will:
- Create the necessary AWS infrastructure (VPC, EKS, etc.)
- Generate Kubernetes service configurations
- Deploy the services defined in the manifest to the cluster

### Command-Line Options

```
usage: deploy_env.py [-h] [--env-id ENV_ID] [--output-dir OUTPUT_DIR] manifest
```

- `manifest`: Path to the manifest YAML file (required)
- `--env-id`: Specify a custom environment ID (default: randomly generated)
- `--output-dir`: Directory to store generated files (default: temporary directory)

### Example

```bash
./cli/deploy_env.py cli/sample-manifest.yaml --env-id my-test-env
```

## Manifest File Structure

The manifest file defines both the infrastructure and the services to deploy. Here's an example:

```yaml
name: my-project
region: eu-west-2

# Services to deploy
services:
  - name: backend-api
    image: my-registry/backend:latest
    port: 8080
    replicas: 1
    expose: true  # Create ingress for this service
  
  - name: frontend
    image: my-registry/frontend:latest
    port: 3000
    replicas: 1
    expose: true

# Infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
  
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
    instance_class: mq.t3.micro
```

### Service Configuration Options

Each service in the manifest can have these properties:

- `name`: Name of the service (required)
- `image`: Docker image to use (required)
- `port`: Container port (default: 8080)
- `replicas`: Number of replicas (default: 1)
- `expose`: Whether to create an ingress for this service (default: true)

### Infrastructure Dependencies

The following dependency types are supported:

- `database`: AWS RDS database
  - `provider`: Database engine (postgres, mysql)
  - `version`: Engine version
  - `storage`: Allocated storage in GB
  - `instance_class`: RDS instance class
  
- `queue`: Amazon MQ message broker
  - `provider`: Message broker type (RabbitMQ)
  - `version`: Engine version
  - `instance_class`: Instance class

## Environment Information

After deployment, information about the environment is saved to the working directory in `env_info.json`. This includes:

- Environment ID
- Project name
- Creation timestamp
- Full manifest content
- Terraform outputs (connection information)
- Working directory location 