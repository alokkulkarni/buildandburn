# Sample PostgreSQL Application

This is a sample Flask application that demonstrates how to connect to a PostgreSQL database and deploy using BuildAndBurn.

## Deployment

The application can be deployed using the unified deployment script `deploy.sh`. This script:

1. Builds the Docker image for the application
2. Creates an ECR repository and pushes the image
3. Updates the manifest file with the correct ECR path
4. Adds the `k8s_path` parameter to the manifest file to identify Kubernetes resources
5. Uses BuildAndBurn to provision AWS infrastructure (including EKS cluster, RDS database, and ingress controller)
6. Deploys the application to Kubernetes
7. Displays access information when completed

### Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed and running
- Python 3.x

### Usage

To deploy the application with default settings:

```bash
./deploy.sh
```

### Customization Options

You can customize the deployment by setting environment variables:

```bash
# Set a specific environment ID (for tracking and cleanup)
ENV_ID=my-env-123 ./deploy.sh

# Use a different AWS region
AWS_REGION=us-east-1 ./deploy.sh

# Use a different manifest file
MANIFEST_FILE=../examples/custom-manifest.yaml ./deploy.sh

# Customize the image name and tag
IMAGE_NAME=my-postgres-app IMAGE_TAG=v1.0 ./deploy.sh
```

### Understanding the Manifest

The deployment script modifies the manifest file to add:

1. **The ECR image path**: Updates the image reference to use the correct ECR repository.
2. **The k8s_path**: Adds a `k8s_path` parameter pointing to the `sample-app/k8s` directory.

The `k8s_path` parameter tells BuildAndBurn where to find the Kubernetes resources. It will:
- Use Helm charts if it finds `Chart.yaml` in the directory
- Use plain Kubernetes manifests from the `manifests` subdirectory if no Helm chart is found
- All resource substitutions (like database credentials) are handled automatically

### Getting Deployment Information

After deployment, the script automatically displays access information. To view this information again:

```bash
# Replace ENV_ID with your environment ID
python3 -m cli.buildandburn info --env-id ENV_ID --detailed
```

### Cleaning Up

To remove all AWS resources created during deployment:

```bash
# Replace ENV_ID with your environment ID
python3 -m cli.buildandburn down --env-id ENV_ID --auto-approve
```

## Application Details

This Flask application exposes the following endpoints:

- `GET /health`: Health check endpoint
- `GET /api/data`: Get all data entries
- `POST /api/data`: Create a new data entry
- `GET /api/data/{id}`: Get a specific data entry
- `DELETE /api/data/{id}`: Delete a data entry

The application connects to a PostgreSQL database using environment variables for configuration. 