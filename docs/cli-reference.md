# CLI Reference

This document provides a reference for all the available commands in the Build and Burn CLI tool.

## Global Flags

These flags can be used with any command:

| Flag | Description |
|------|-------------|
| `--version` | Show the version of the Build and Burn CLI tool. |
| `--help` | Show help information for the command. |

## Commands

### `buildandburn up`

Creates a new build-and-burn environment based on a manifest file.

#### Usage

```bash
buildandburn up <manifest-file> [options]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `manifest-file` | Yes | Path to the manifest YAML file that defines the environment. |

#### Options

| Option | Description |
|--------|-------------|
| `--env-id <id>` | Custom environment ID to use. If not specified, a random ID will be generated. |
| `--keep-local` | Keep local files after destruction. |

#### Example

```bash
buildandburn up my-app.yaml
```

### `buildandburn down`

Destroys an existing build-and-burn environment.

#### Usage

```bash
buildandburn down <env-id> [options]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `env-id` | Yes | The ID of the environment to destroy. |

#### Options

| Option | Description |
|--------|-------------|
| `--keep-local` | Keep local files after destruction. |

#### Example

```bash
buildandburn down a1b2c3d4
```

### `buildandburn info`

Displays information about an existing build-and-burn environment.

#### Usage

```bash
buildandburn info <env-id>
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `env-id` | Yes | The ID of the environment to get information about. |

#### Example

```bash
buildandburn info a1b2c3d4
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

## Alternative Command (bb-deploy)

The Build and Burn CLI tool also provides an alternative command `bb-deploy` for deploying environments directly without using the command structure. This is primarily used for backward compatibility and scripts.

#### Usage

```bash
bb-deploy <manifest-file> [options]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `manifest-file` | Yes | Path to the manifest YAML file that defines the environment. |

#### Options

| Option | Description |
|--------|-------------|
| `--env-id <id>` | Custom environment ID to use. If not specified, a random ID will be generated. |
| `--output-dir <dir>` | Directory to output temporary files. If not specified, a temporary directory will be created. |

#### Example

```bash
bb-deploy my-app.yaml
```

## Environment Variables

The Build and Burn CLI tool respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `AWS_PROFILE` | The AWS profile to use for credentials. |
| `AWS_REGION` | The AWS region to use. This will override the region specified in the manifest file. |
| `BUILDANDBURN_DEBUG` | Set to `1` to enable debug output. |
| `BUILDANDBURN_HOME` | The directory to store environment files. Defaults to `~/.buildandburn`. |

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