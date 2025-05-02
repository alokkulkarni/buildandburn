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
3. Deploy your services
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

# Services to deploy
services:
  - name: backend
    image: my-backend:latest
    port: 8080
    replicas: 2
    expose: true
    
  - name: frontend
    image: my-frontend:latest
    port: 80
    replicas: 1
    expose: true

# Optional infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "13"
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
```

## Accessing Services

Once the environment is created, you can access your services at the URLs provided in the `info` action output. These URLs are also available in the workflow logs.

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

### Debugging

The workflow uploads logs as artifacts, which you can download and examine after the workflow completes:

1. Go to the workflow run
2. Scroll to the bottom and look for "Artifacts"
3. Download the "buildandburn-logs" artifact
4. Extract and examine the logs for detailed error information 