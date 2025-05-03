# Build and Burn Environment: ${{ values.name }}

This repository contains configuration for a disposable Kubernetes environment managed by the Build and Burn system.

## Prerequisites

To use this environment, you need:

1. GitHub account with access to this repository
2. AWS credentials with appropriate permissions

## Using the Environment

### Creating the Environment

To create the environment:

1. Go to the **Actions** tab in this repository
2. Select the **Build and Burn Environment** workflow
3. Click **Run workflow**
4. Configure the workflow:
   - **Action**: `up`
   - **Manifest Path**: `manifest.yaml` (or your custom path)
   - **No Generate K8s**: Set to true if using custom Kubernetes resources
   - **Dry Run**: Set to true to validate without creating resources
5. Click **Run workflow**

The workflow will:
1. Provision the necessary AWS infrastructure
2. Create a Kubernetes cluster
3. Deploy your services with NGINX ingress controller
4. Display access information when complete

### Viewing Environment Information

To get information about the environment:

1. Go to the **Actions** tab in this repository
2. Select the **Build and Burn Environment** workflow
3. Click **Run workflow**
4. Configure the workflow:
   - **Action**: `info`
   - **Env ID**: Your environment ID (found in the output of the creation workflow)
5. Click **Run workflow**

### Listing All Environments

To list all environments:

1. Go to the **Actions** tab in this repository
2. Select the **Build and Burn Environment** workflow
3. Click **Run workflow**
4. Configure the workflow:
   - **Action**: `list`
5. Click **Run workflow**

### Destroying the Environment

When you're done with the environment, you can destroy it:

1. Go to the **Actions** tab in this repository
2. Select the **Build and Burn Environment** workflow
3. Click **Run workflow**
4. Configure the workflow:
   - **Action**: `down`
   - **Env ID**: Your environment ID
5. Click **Run workflow**

## Environment Configuration

The environment is defined in the `manifest.yaml` file in this repository. You can modify this file to change the configuration of your environment.

### Manifest Structure

```yaml
name: my-environment
region: eu-west-2
k8s_path: path/to/custom/k8s  # Optional: custom path to Kubernetes manifests

# Services to deploy
services:
  - name: backend
    image: my-backend:latest
    port: 8080
    replicas: 2
    expose: true
    # Ingress is automatically configured when expose is true
    
  - name: frontend
    image: my-frontend:latest
    port: 80
    replicas: 1
    expose: true

# Optional infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "15"  # Latest stable PostgreSQL version
  - type: queue
    provider: rabbitmq
    version: "3.13"
```

## Accessing Services

Once the environment is created, you can access your services at the URLs provided in the `info` action output. These URLs are also available in the workflow logs.

For services exposed via the NGINX ingress controller, you'll get both an ingress controller URL and the hostname configured for the service. You may need to:

1. Configure DNS to point the hostname to the ingress controller's load balancer, or
2. Use the Host header with the ingress controller URL for testing:
   ```
   curl -H "Host: backend.my-environment.example.com" http://ingress-controller-url/path
   ```

## Working with ECR Images

### Using Images from ECR

When using container images from Amazon ECR, the EKS cluster is configured with the necessary permissions to pull images from:

1. ECR repositories in the same AWS account
2. ECR repositories in other AWS accounts (cross-account access)

To reference an ECR image in your manifest:

```yaml
services:
  - name: my-service
    image: 123456789012.dkr.ecr.us-west-2.amazonaws.com/my-repository:latest
    # other configuration...
```

### Cross-Account ECR Access

If you need to pull images from ECR repositories in a different AWS account:

1. The EKS cluster has the IAM permissions required to pull from other accounts
2. The ECR repository in the other account must have a repository policy that allows access from your account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:root"
      },
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ]
    }
  ]
}
```

The GitHub workflow will attempt to authenticate to cross-account ECR repositories automatically when it detects ECR image references in your manifest.

## Customizing with GitHub Actions

You can customize the workflow by editing the `.github/workflows/buildandburn.yml` file. For example, to add notification when an environment is created:

```yaml
- name: Notify Slack
  if: ${{ github.event.inputs.action == 'up' && success() }}
  uses: someSlackAction/slack-notify@v1
  with:
    channel: deployments
    message: "Environment created successfully"
```

## Troubleshooting

### Common Issues

1. **Missing AWS credentials**: Ensure you've added the required secrets to your GitHub repository
2. **Permission errors**: Check that your AWS credentials have sufficient permissions
3. **Missing manifest file**: Verify the path to your manifest file is correct
4. **Ingress not working**: Check that the NGINX ingress controller was properly deployed and that your service's ingress configuration is correct
5. **ECR image pull failures**: For cross-account ECR access, ensure the repository policy in the source account grants access to your account

### Debugging

The workflow uploads logs as artifacts, which you can download and examine after the workflow completes:

1. Go to the workflow run
2. Scroll to the bottom and look for "Artifacts"
3. Download the "buildandburn-logs" artifact
4. Extract and examine the logs for detailed error information

## Recent Updates

This template has been updated with several important improvements:

1. **NGINX Ingress Controller** - Services marked with `expose: true` are now automatically accessible via the NGINX ingress controller, providing a more robust and production-ready routing solution.

2. **PostgreSQL 15 Support** - The template now defaults to PostgreSQL 15 for database dependencies, ensuring compatibility with AWS RDS.

3. **Enhanced Deployment Process** - The GitHub Actions workflow now:
   - Automatically builds and pushes Docker images to ECR
   - Waits for resources to be available before proceeding
   - Tests the deployed applications to verify functionality
   - Provides detailed deployment status information

4. **Customizable Kubernetes Resources** - Better support for providing custom Kubernetes manifests via the `k8s_path` parameter.

5. **ECR Cross-Account Access** - Added support for pulling container images from ECR repositories in different AWS accounts.

These improvements ensure a smoother, more reliable deployment experience with better observability and production-ready configurations. 