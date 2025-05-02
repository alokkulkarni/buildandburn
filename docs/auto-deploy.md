# GitHub Actions Integration

Build and Burn provides GitHub Actions workflows for creating, managing, and destroying environments directly from your GitHub repository. This enables teams to automate the deployment of disposable environments for testing, development, and demonstration purposes.

## Available Workflows

The following GitHub Actions workflow files are included in the `.github/workflows` directory:

1. **buildandburn.yml**: For manual creation and management of environments
2. **ci.yml**: For continuous integration testing of the Build and Burn codebase

## Using the BuildAndBurn Workflow

The `buildandburn.yml` workflow allows you to manually trigger environment operations using GitHub's workflow dispatch feature.

### Workflow Inputs

When triggering the workflow, you can specify the following inputs:

| Input | Description | Default |
|-------|-------------|---------|
| `action` | Action to perform (`up`, `down`, `info`, `list`) | `up` |
| `manifest_path` | Path to the manifest file | `manifest.yaml` |
| `env_id` | Environment ID (required for `down` and `info` actions) | - |
| `no_generate_k8s` | Skip K8s resource generation | `false` |
| `dry_run` | Validate configuration without creating resources | `false` |

### Required Secrets

To use the workflow, you need to configure the following GitHub repository secrets:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key with permissions to create required resources |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key matching the above access key |
| `AWS_REGION` | AWS region to deploy to (optional, defaults to `eu-west-2`) |

### Example Usage

#### Creating an Environment

1. Navigate to the "Actions" tab in your GitHub repository
2. Select the "Build and Burn Environment" workflow
3. Click "Run workflow"
4. Enter the following parameters:
   - **Action**: `up`
   - **Manifest Path**: Path to your manifest.yaml file
   - **No Generate K8s**: Set to true if using custom K8s templates
   - **Dry Run**: Set to true to validate without creating resources
5. Click "Run workflow"

#### Getting Environment Information

1. Navigate to the "Actions" tab in your GitHub repository
2. Select the "Build and Burn Environment" workflow
3. Click "Run workflow"
4. Enter the following parameters:
   - **Action**: `info`
   - **Env ID**: Your environment ID
5. Click "Run workflow"

#### Destroying an Environment

1. Navigate to the "Actions" tab in your GitHub repository
2. Select the "Build and Burn Environment" workflow
3. Click "Run workflow"
4. Enter the following parameters:
   - **Action**: `down`
   - **Env ID**: Your environment ID
5. Click "Run workflow"

## Workflow Implementation Details

The workflow performs the following steps:

1. Sets up Python, Terraform, kubectl, and Helm 
2. Configures AWS credentials
3. Runs the requested action using the Build and Burn CLI
4. Uploads logs as artifacts for future reference

Here's a snippet of the key parts of the workflow:

```yaml
- name: Create environment
  if: ${{ github.event.inputs.action == 'up' }}
  run: |
    # Set flags based on inputs
    EXTRA_FLAGS=""
    if [ "${{ github.event.inputs.no_generate_k8s }}" == "true" ]; then
      EXTRA_FLAGS="$EXTRA_FLAGS --no-generate-k8s"
    fi
    
    if [ "${{ github.event.inputs.dry_run }}" == "true" ]; then
      EXTRA_FLAGS="$EXTRA_FLAGS --dry-run"
    fi
    
    # Run the command with all flags
    buildandburn up --manifest ${{ github.event.inputs.manifest_path }} $EXTRA_FLAGS
```

## Continuous Integration Workflow

The `ci.yml` workflow is used for testing the Build and Burn codebase itself. It runs on every push to the main branch and pull requests, performing the following tasks:

1. Runs unit tests across multiple Python versions
2. Validates Terraform configurations
3. Performs integration tests including dry-run tests
4. Builds and publishes the Python package (on tagged releases)

## Customizing the Workflows

### Adding Custom Steps

You can customize the GitHub Actions workflows by adding your own steps. For example, to add notification when an environment is created:

```yaml
- name: Notify Slack
  if: ${{ github.event.inputs.action == 'up' && success() }}
  uses: someSlackAction/slack-notify@v1
  with:
    channel: deployments
    message: "Environment created successfully"
```

### Running on Schedule

To automatically create environments on a schedule, you can add a schedule trigger:

```yaml
on:
  workflow_dispatch:
    # ... existing inputs
  schedule:
    - cron: '0 8 * * 1'  # Every Monday at 8am
```

### Using Environment Outputs

The Build and Burn CLI outputs information about created environments. You can capture and use this information in subsequent workflow steps:

```yaml
- name: Create environment
  id: create-env
  if: ${{ github.event.inputs.action == 'up' }}
  run: |
    output=$(buildandburn up --manifest ${{ github.event.inputs.manifest_path }})
    echo "::set-output name=env_url::$(echo "$output" | grep "APPLICATION URL" | awk '{print $3}')"

- name: Use environment URL
  if: ${{ github.event.inputs.action == 'up' }}
  run: |
    echo "Environment created at ${{ steps.create-env.outputs.env_url }}"
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