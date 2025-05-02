# CLI Reference

This document provides a reference for all the available commands in the Build and Burn CLI tool.

## Global Flags

These flags can be used with any command:

| Flag | Description |
|------|-------------|
| `--version` | Show the version of the Build and Burn CLI tool. |
| `--help` | Show help information for the command. |
| `--debug` | Enable debug mode for verbose output. |

## Commands

### `buildandburn up`

Creates a new build-and-burn environment based on a manifest file.

#### Usage

```bash
buildandburn up --manifest <manifest-file> [options]
```

#### Arguments

| Option | Required | Description |
|----------|----------|-------------|
| `--manifest <path>` | Yes | Path to the manifest YAML file that defines the environment. |
| `--env-id <id>` | No | Custom environment ID to use. If not specified, a random ID will be generated. |
| `--no-generate-k8s` | No | Skip generating Kubernetes resources. Use this when providing a custom `k8s_path` in the manifest. |
| `--auto-approve` | No | Skip confirmation prompts for Terraform operations. |
| `--dry-run` | No | Validate configuration without creating resources. |

#### Example

```bash
buildandburn up --manifest my-app.yaml
```

### `buildandburn down`

Destroys an existing build-and-burn environment.

#### Usage

```bash
buildandburn down --env-id <env-id> [options]
```

#### Arguments

| Option | Required | Description |
|----------|----------|-------------|
| `--env-id <id>` | Yes | The ID of the environment to destroy. |
| `--force` | No | Force destruction even if errors occur. |
| `--auto-approve` | No | Skip confirmation prompts for Terraform destroy operations. |
| `--keep-local` | No | Keep local files after destruction. |

#### Example

```bash
buildandburn down --env-id a1b2c3d4
```

### `buildandburn info`

Displays information about an existing build-and-burn environment.

#### Usage

```bash
buildandburn info --env-id <env-id>
```

#### Arguments

| Option | Required | Description |
|----------|----------|-------------|
| `--env-id <id>` | Yes | The ID of the environment to get information about. |

#### Example

```bash
buildandburn info --env-id a1b2c3d4
```

### `buildandburn list`

Lists all build-and-burn environments.

#### Usage

```bash
buildandburn list
```

#### Example

```bash
buildandburn list
```

## Environment Variables

The Build and Burn CLI tool respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `AWS_PROFILE` | The AWS profile to use for credentials. |
| `AWS_REGION` | The AWS region to use. This will override the region specified in the manifest file. |
| `AWS_ACCESS_KEY_ID` | AWS access key for authentication. |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for authentication. |
| `BUILDANDBURN_DEBUG` | Set to `1` to enable debug output. |
| `BUILDANDBURN_HOME` | The directory to store environment files. Defaults to `~/.buildandburn`. |
| `BUILDANDBURN_IGNORE_MISSING_PREREQUISITES` | Set to `1` to ignore missing prerequisites checks. |
| `TF_PLUGIN_CACHE_DIR` | Directory for caching Terraform plugins. |

## Configuration Files

### Environment Information

Environment information is stored in `~/.buildandburn/<env-id>/env_info.json` and contains:

- Environment ID
- Project name
- Creation timestamp
- AWS region
- Terraform outputs
- Access information (service endpoints, database connections, etc.)
- Resource estimates and costs

## Return Codes

The Build and Burn CLI tool uses the following return codes:

| Code | Description |
|------|-------------|
| `0` | Command completed successfully. |
| `1` | General error. |
| `2` | Invalid command or argument. |
| `3` | Environment not found. |
| `4` | Terraform error. |
| `5` | Kubernetes error. |

## Using in GitHub Actions

The CLI can be used in GitHub Actions workflows using the following structure:

```yaml
jobs:
  buildandburn:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        
      - name: Set up dependencies
        # ... (install Python, Terraform, kubectl, etc)
          
      - name: Create environment
        run: |
          buildandburn up --manifest ${{ github.event.inputs.manifest_path }}
```

For a complete example, see the [GitHub Actions documentation](./auto-deploy.md). 