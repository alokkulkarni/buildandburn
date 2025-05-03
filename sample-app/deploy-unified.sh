#!/bin/bash
# Unified Deployment Script for BuildAndBurn
# This script builds and deploys the sample application with full infrastructure provisioning

set -e

# Get the script directory in a cross-platform way
get_script_dir() {
  # Try to use readlink if available (Linux)
  if command -v readlink >/dev/null 2>&1 && readlink -f "$0" >/dev/null 2>&1; then
    dirname "$(readlink -f "$0")"
  else
    # Fallback for macOS and other systems
    local SOURCE="$0"
    while [ -h "$SOURCE" ]; do
      local DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
      SOURCE="$(readlink "$SOURCE")"
      [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
    done
    cd -P "$( dirname "$SOURCE" )" && pwd
  fi
}

# Configuration
ENV_ID="${ENV_ID:-$(date +%s)}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
MANIFEST_FILE="${MANIFEST_FILE:-examples/test-manifest.yaml}"
SAMPLE_APP_DIR=$(get_script_dir)
REPO_ROOT=$(dirname "$SAMPLE_APP_DIR")

# Ensure paths are absolute
if [[ "$MANIFEST_FILE" != /* ]]; then
  MANIFEST_FILE="$REPO_ROOT/$MANIFEST_FILE"
fi

MANIFEST_TEMP="$REPO_ROOT/examples/temp-manifest-${ENV_ID}.yaml"

# App configuration
IMAGE_NAME="${IMAGE_NAME:-postgres-app}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "========================================================"
echo "  BuildAndBurn Unified Deployment"
echo "========================================================"
echo "Environment ID: $ENV_ID"
echo "AWS Region: $AWS_REGION"
echo "Manifest: $MANIFEST_FILE"
echo "App directory: $SAMPLE_APP_DIR"

# Validate manifest file exists
if [ ! -f "$MANIFEST_FILE" ]; then
  echo "Error: Manifest file not found: $MANIFEST_FILE"
  echo "Please specify a valid manifest file with MANIFEST_FILE environment variable."
  exit 1
fi

# Check if required tools are installed
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is not installed."; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "Error: AWS CLI is not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 is not installed."; exit 1; }

# Get AWS account ID
echo "Getting AWS account information..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
  echo "Error: Failed to get AWS account ID. Are you logged in to AWS CLI?"
  echo "Run 'aws configure' to set up your AWS credentials."
  exit 1
fi

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
echo "ECR Registry: $ECR_REGISTRY"

# Create ECR repository if it doesn't exist
echo "Creating ECR repository (if it doesn't exist)..."
aws ecr describe-repositories --repository-names $IMAGE_NAME --region $AWS_REGION >/dev/null 2>&1 || \
aws ecr create-repository --repository-name $IMAGE_NAME --region $AWS_REGION

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build Docker image
echo "Building Docker image..."
cd "$SAMPLE_APP_DIR"
docker build -t $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG .

# Push to ECR
echo "Pushing Docker image to ECR..."
docker push $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG
echo "Image pushed successfully: $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"

# Create a modified manifest with the correct ECR path
echo "Updating manifest with ECR path..."
cd "$REPO_ROOT"
cp "$MANIFEST_FILE" "$MANIFEST_TEMP"

# Update the image path in the manifest using sed
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS version of sed requires different syntax
  sed -i '' "s|image:.*$IMAGE_NAME:.*|image: $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" "$MANIFEST_TEMP"
else
  # Linux version of sed
  sed -i "s|image:.*$IMAGE_NAME:.*|image: $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" "$MANIFEST_TEMP"
fi

echo "Using modified manifest: $MANIFEST_TEMP"

# Deploy infrastructure and application using BuildAndBurn
echo "Deploying infrastructure and application with BuildAndBurn..."
python3 -m cli.buildandburn up --manifest "$MANIFEST_TEMP" --env-id "$ENV_ID" --auto-approve

# Show deployment information
echo "========================================================"
echo "Retrieving deployment information..."
python3 -m cli.buildandburn info --env-id "$ENV_ID" --detailed

echo "========================================================"
echo "DEPLOYMENT COMPLETE!"
echo "Environment ID: $ENV_ID"
echo ""
echo "The application should now be accessible via the URLs shown above."
echo ""
echo "To clean up all resources when finished:"
echo "python3 -m cli.buildandburn down --env-id $ENV_ID --auto-approve"
echo "========================================================"

# Clean up temporary manifest
rm -f "$MANIFEST_TEMP" 