# Build and Burn CLI

The Build and Burn CLI is a powerful tool for creating and managing disposable development and testing environments. It provides a simple interface for provisioning infrastructure, deploying services, and cleaning up resources when no longer needed.

## Installation

### Prerequisites

Before installing the CLI tool, ensure you have the following prerequisites:

1. **Python 3.7+**
2. **AWS CLI**: Configured with appropriate credentials
3. **Terraform**: Version 1.0.0 or later
4. **kubectl**: For interacting with Kubernetes clusters

### Install from PyPI

```bash
pip install buildandburn
```

### Install from Source

```bash
git clone https://github.com/yourusername/buildandburn.git
cd buildandburn/cli
pip install -e .
```

## Configuration

The CLI tool uses the following configuration sources in order of precedence:

1. Command-line arguments
2. Environment variables
3. Configuration file (~/.buildandburn/config.yaml)

### AWS Credentials

Build and Burn uses your AWS credentials to provision infrastructure. Configure them using:

1. AWS CLI: `aws configure`
2. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
3. AWS profiles: `~/.aws/credentials`

## Creating a Manifest

A manifest file defines the services and infrastructure required for your environment. Create a file named `manifest.yaml` with the following structure:

```yaml
name: my-project
region: us-west-2

# Services to deploy
services:
  - name: backend-api
    image: my-registry/backend:latest
    port: 8080
    replicas: 1
  
  - name: frontend
    image: my-registry/frontend:latest
    port: 3000
    replicas: 1

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

## Basic Usage

### Create an Environment

```bash
buildandburn up --manifest manifest.yaml
```

This command:
1. Provisions the necessary infrastructure based on your manifest
2. Deploys the specified services
3. Outputs connection information for the environment

### List Environments

```bash
buildandburn list
```

This command lists all your build-and-burn environments, including their IDs, names, and creation times.

### Get Environment Information

```bash
buildandburn info --env-id <environment-id>
```

Retrieves and displays detailed information about a specific environment, including:
- Service endpoints
- Database connection details
- Message queue connection details

### Destroy an Environment

```bash
buildandburn down --env-id <environment-id>
```

This command:
1. Terminates all services running in the environment
2. Deprovisions all infrastructure resources
3. Cleans up any local files associated with the environment

Add the `--force` flag to skip confirmation prompts.

## Advanced Usage

### Custom Environment ID

```bash
buildandburn up --manifest manifest.yaml --env-id my-custom-id
```

### Keep Local Files After Destruction

```bash
buildandburn down --env-id <environment-id> --keep-files
```

## Environment Storage

Build and Burn stores environment information in `~/.buildandburn/<env-id>/` directories. Each directory contains:

- `env_info.json`: Metadata about the environment
- `terraform/`: Terraform state and configuration
- `kubeconfig`: Kubernetes configuration for the environment
- `values.yaml`: Values used for Kubernetes deployments

## Troubleshooting

### Common Issues

1. **Missing prerequisites**: Ensure Terraform, kubectl, and AWS CLI are installed and in your PATH
2. **AWS credential errors**: Verify AWS credentials are properly configured
3. **Terraform state errors**: Check the Terraform state in `~/.buildandburn/<env-id>/terraform/`

### Debug Mode

For more detailed output, use the debug flag:

```bash
buildandburn --debug up --manifest manifest.yaml
```

## Contributing

Contributions to the CLI tool are welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines on how to contribute.

## License

MIT 