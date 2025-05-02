# Build and Burn Backstage Plugin: GitHub Actions Integration

This document explains how to use the GitHub Actions integration in the Build and Burn Backstage plugin.

## Overview

The Build and Burn Backstage plugin includes direct integration with GitHub Actions, allowing you to:

1. Trigger GitHub Actions workflows to create and manage environments
2. Monitor GitHub Actions workflow runs in real-time
3. View detailed logs from workflow jobs
4. Connect environments to their source GitHub repositories

## Prerequisites

Before using the GitHub Actions integration, you need:

1. A Backstage instance with the Build and Burn plugin installed
2. GitHub repositories with the Build and Burn workflow file (`.github/workflows/buildandburn.yml`)
3. A GitHub personal access token with `repo` and `workflow` scopes
4. AWS credentials configured as GitHub repository secrets

## Configuration

### Backstage Configuration

Add the following to your Backstage `app-config.yaml`:

```yaml
github:
  token: ${GITHUB_TOKEN}

backend:
  baseUrl: http://localhost:7007
```

### GitHub Repository Configuration

Ensure your GitHub repository has:

1. A workflow file at `.github/workflows/buildandburn.yml` (see the [template](../../backstage-plugin/templates/workflow.yaml))
2. The following secrets configured:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION` (optional, defaults to `eu-west-2`)

## Creating an Environment with GitHub Actions

1. Navigate to the Build and Burn page in your Backstage portal
2. Click the "Create Environment" button
3. Select the "GitHub Actions" tab
4. Fill in the following details:
   - **Repository Owner**: GitHub organization or user name
   - **Repository Name**: GitHub repository name
   - **Action**: Select "Create Environment (up)"
   - **Manifest Path**: Path to the manifest YAML file in the repository
   - **Skip K8s Generation** (optional): Check if using custom Kubernetes resources
   - **Dry Run** (optional): Check to validate without creating resources
5. Click "Trigger Workflow"

The plugin will automatically:
- Trigger the workflow in your GitHub repository
- Track the workflow run
- Switch to the GitHub Workflows tab to show progress

## Monitoring Workflow Runs

After triggering a workflow, you can monitor its progress:

1. In the Build and Burn page, click the "GitHub Workflows" tab
2. View all workflow runs for the repository
3. Check the status of each run (queued, in progress, completed)
4. Click "View Logs" to see detailed logs for a specific run
5. Click "Refresh" to update the status of active runs

The plugin automatically polls for updates to active workflow runs every 10 seconds.

## Viewing Workflow Logs

To view logs for a workflow run:

1. Click "View Logs" on a workflow run
2. The logs will show output from all jobs in the workflow
3. If the workflow is still running, click "Refresh" to get the latest logs

## Destroying an Environment with GitHub Actions

To destroy an environment using GitHub Actions:

1. In the Environments tab, find the environment you want to destroy
2. Click the "Destroy" button
3. If the environment is linked to a GitHub repository, the plugin will:
   - Trigger the GitHub workflow with the `down` action
   - Pass the environment ID to the workflow
   - Track the workflow run in the GitHub Workflows tab

## Getting Environment Information

To get information about an existing environment:

1. Click the "Workflows" button on an environment
2. In the GitHub Workflows tab, select the "Create Environment (up)" workflow
3. Click "View Logs" to see the detailed output, including environment information

## Troubleshooting

If you encounter issues with the GitHub Actions integration:

### Workflow Not Found

If you see "Workflow not found" errors:
- Ensure the repository has a file at `.github/workflows/buildandburn.yml`
- Check that your GitHub token has the `repo` and `workflow` scopes
- Verify the repository owner and name are correct

### Authentication Issues

If you see authentication errors:
- Check that your GitHub token is valid and has the required scopes
- Ensure the token is correctly configured in `app-config.yaml`
- Verify you have access to the repository

### Workflow Fails to Run

If the workflow fails:
- Check the workflow logs for specific error messages
- Verify that AWS credentials are correctly configured as repository secrets
- Check that the manifest file path is correct

## Best Practices

1. **Use Environment IDs**: Always save environment IDs for later destruction
2. **Monitor Active Runs**: Keep the GitHub Workflows tab open while workflows are running
3. **Destroy Unused Environments**: To avoid unnecessary costs, destroy environments when they are no longer needed
4. **Use Dry Run**: Use the dry run option to validate your configuration before creating resources

## Contributing

For information on contributing to the Build and Burn project, please see the [CONTRIBUTING.md](../../CONTRIBUTING.md) file in the root of the repository. 