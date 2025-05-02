# Using the Build and Burn Backstage Template

The Build and Burn Backstage template allows you to quickly create new disposable Kubernetes environments that can be managed with GitHub Actions. This guide explains how to use the template within your Backstage instance.

## Prerequisites

Before using the template, ensure you have:

1. A Backstage instance with the Scaffolder plugin installed
2. The Build and Burn Backstage plugin installed in your Backstage instance
3. GitHub integration configured in your Backstage instance
4. AWS credentials for deploying environments

## Accessing the Template

1. Go to your Backstage portal
2. Navigate to **Create...** in the sidebar
3. Look for **Build and Burn Environment** in the template list
4. Click on the template card to start the creation process

## Using the Template

The template wizard will guide you through the following steps:

### Step 1: Repository Information

- **GitHub Organization**: Select the GitHub organization where the repository will be created
- **Repository Name**: Enter a name for the repository that will contain your environment configuration

### Step 2: Environment Configuration

- **Environment Name**: Enter a name for your environment (used in resource naming)
- **AWS Region**: Select the AWS region where the environment will be deployed (default: eu-west-2)

### Step 3: Service Configuration

Define the services to deploy in your environment:

- **Service Name**: Name of the service (used in Kubernetes resource naming)
- **Container Image**: Docker image to use for this service
- **Port**: Port the service listens on
- **Replicas**: Number of replicas to deploy
- **Expose Service**: Whether to expose the service externally
- **Service Type**: Kubernetes service type (ClusterIP, LoadBalancer, NodePort)

You can add multiple services by clicking the "Add Item" button.

### Step 4: Infrastructure Dependencies (Optional)

Add optional infrastructure dependencies such as databases, message queues, or caches:

- **Dependency Type**: Type of dependency (database, queue, cache, storage)
- **Provider**: Provider to use for this dependency (postgres, mysql, rabbitmq, redis, s3)
- **Version**: Version of the dependency
- **Storage (GB)**: Storage size for database or storage dependencies
- **Instance Class**: AWS instance class for the dependency

### Step 5: Kubernetes Configuration (Optional)

- **Custom Kubernetes Resources Path**: Path to custom Kubernetes resources (leave empty to generate automatically)
- **Skip K8s Generation**: Skip Kubernetes resource generation (use with customK8sPath)
- **Dry Run**: Validate configuration without creating resources

### Step 6: CI/CD Configuration

- **Setup GitHub Action**: Create GitHub Actions workflow to manage environments

## What the Template Creates

After completing the wizard, the template will:

1. Create a new GitHub repository
2. Generate a manifest file based on your configuration
3. Setup a GitHub Actions workflow for managing the environment
4. Create a README with usage instructions
5. Configure GitHub repository secrets for AWS integration

## Managing the Environment

Once the template has completed, you can manage your environment through:

1. **GitHub Actions**: Use the workflow in the created repository to create, destroy, and manage environments
2. **Build and Burn Plugin**: Use the Backstage plugin to view and manage environments

## Workflow Commands

The generated repository includes GitHub Actions workflows that support the following commands:

```bash
# Create an environment
gh workflow run buildandburn.yml -f action=up -f manifestPath=manifest.yaml

# Get information about an environment
gh workflow run buildandburn.yml -f action=info -f envId=<environment-id>

# List all environments
gh workflow run buildandburn.yml -f action=list

# Destroy an environment
gh workflow run buildandburn.yml -f action=down -f envId=<environment-id>
```

## Troubleshooting

If you encounter issues with the template or the created environment:

1. **Template Errors**: Check the output of the template scaffolding process for error messages
2. **GitHub Repository**: Ensure the repository was created successfully
3. **GitHub Actions**: Check the GitHub Actions workflow for error messages
4. **AWS Credentials**: Ensure AWS credentials are correctly configured in GitHub repository secrets

## Example Workflow

Here's a typical workflow for using the template:

1. Use the template to create a new environment configuration
2. Go to the created GitHub repository
3. Run the GitHub Actions workflow to create the environment
4. Use the environment for development or testing
5. When finished, run the workflow again to destroy the environment

## Contributing

For information on contributing to the Build and Burn project, please see the [CONTRIBUTING.md](../../CONTRIBUTING.md) file in the root of the repository. 