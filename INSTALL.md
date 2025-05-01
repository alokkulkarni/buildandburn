# Build and Burn - Installation Guide

This guide covers how to install the Build and Burn CLI tool and set up your environment for creating disposable development and testing environments.

## Prerequisites

Before installing Build and Burn, ensure you have the following prerequisites:

1. **Python 3.7+** - The CLI tool requires Python 3.7 or higher.
2. **AWS CLI** - Configured with appropriate credentials.
3. **Terraform** - Version 1.0.0 or higher.
4. **kubectl** - For interacting with Kubernetes clusters.
5. **Helm** - For deploying applications to Kubernetes.

## Installation Methods

### Option 1: Install from PyPI (Recommended)

The easiest way to install the Build and Burn CLI tool is using pip:

```bash
pip install buildandburn
```

### Option 2: Install from Source

To install from source:

1. Clone the repository:

```bash
git clone https://github.com/your-org/buildandburn.git
cd buildandburn
```

2. Install the CLI tool:

```bash
pip install -e ./cli
```

## Configuration

### AWS Credentials

Ensure your AWS credentials are properly configured:

```bash
aws configure
```

You'll need to set up:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (recommended: eu-west-2)
- Default output format (json recommended)

### Terraform Backend Configuration

By default, the tool uses local state storage. If you prefer to use S3 for state storage, modify the `terraform/main.tf` file:

```hcl
terraform {
  # ... existing configuration ...
  
  backend "s3" {
    bucket  = "your-terraform-state-bucket"
    key     = "buildandburn/terraform.tfstate"
    region  = "eu-west-2"
    encrypt = true
  }
}
```

## Verification

Verify the installation by running:

```bash
buildandburn --version
```

You should see the version number of the installed Build and Burn CLI tool.

## Next Steps

After installation, follow the [Getting Started](docs/getting-started.md) guide to create your first disposable environment. 