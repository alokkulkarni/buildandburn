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

# Wait for resource function
wait_for_resource() {
  local resource_type=$1
  local resource_name=$2
  local namespace=$3
  local timeout=${4:-300}
  local kubeconfig=$5
  
  echo "Waiting for $resource_type/$resource_name to be ready (timeout: ${timeout}s)..."
  
  local elapsed=0
  local check_interval=10
  
  while [ $elapsed -lt $timeout ]; do
    if KUBECONFIG=$kubeconfig kubectl get $resource_type $resource_name -n $namespace >/dev/null 2>&1; then
      echo "$resource_type/$resource_name exists!"
      
      if [ "$resource_type" == "pod" ] || [ "$resource_type" == "deployment" ]; then
        if KUBECONFIG=$kubeconfig kubectl wait --for=condition=ready $resource_type/$resource_name -n $namespace --timeout=10s >/dev/null 2>&1; then
          echo "$resource_type/$resource_name is ready!"
          return 0
        fi
      else
        # For other resource types, existence is sufficient
        return 0
      fi
    fi
    
    sleep $check_interval
    elapsed=$((elapsed + check_interval))
    echo "Still waiting for $resource_type/$resource_name... ($elapsed/$timeout seconds elapsed)"
  done
  
  echo "Timeout waiting for $resource_type/$resource_name"
  return 1
}

# Test deployed application
test_application() {
  local ingress_url=$1
  local host_header=$2
  local retries=5
  local delay=10
  local curl_opts=""
  
  echo "Testing application at $ingress_url..."
  
  # Add Host header if provided
  if [ -n "$host_header" ]; then
    curl_opts="-H 'Host: $host_header'"
    echo "Using Host header: $host_header"
  fi
  
  # Test health endpoint
  for i in $(seq 1 $retries); do
    echo "Test attempt $i of $retries..."
    
    echo "Testing health endpoint..."
    if eval "curl -s -o /dev/null -w '%{http_code}' $curl_opts ${ingress_url}/health" | grep -q "200"; then
      echo "✅ Health endpoint check passed!"
      
      # Test API functionality
      echo "Testing data API..."
      
      # Create a test record
      echo "Creating test record..."
      test_data='{"message":"Test message from deployment script","data":{"test":true,"timestamp":"'"$(date)"'"}}'
      create_response=$(eval "curl -s -X POST -H 'Content-Type: application/json' $curl_opts -d '$test_data' '${ingress_url}/api/data'")
      
      if echo "$create_response" | grep -q "id"; then
        echo "✅ Data creation successful!"
        
        # Get the ID from the response
        record_id=$(echo "$create_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        
        if [ -n "$record_id" ]; then
          echo "Testing data retrieval with ID: $record_id"
          
          # Retrieve the record
          if eval "curl -s $curl_opts '${ingress_url}/api/data/${record_id}'" | grep -q "$record_id"; then
            echo "✅ Data retrieval successful!"
            return 0
          else
            echo "❌ Data retrieval failed"
          fi
        else
          echo "❌ Failed to extract record ID"
        fi
      else
        echo "❌ Data creation failed: $create_response"
      fi
    else
      echo "❌ Health check failed, retrying in $delay seconds..."
      sleep $delay
    fi
  done
  
  echo "❌ Application tests failed after $retries attempts"
  return 1
}

# Configuration
ENV_ID="${ENV_ID:-$(date +%s)}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
MANIFEST_FILE="${MANIFEST_FILE:-examples/test-manifest.yaml}"
SAMPLE_APP_DIR=$(get_script_dir)
REPO_ROOT=$(dirname "$SAMPLE_APP_DIR")
MAX_WAIT=600 # 10 minutes timeout for resource validation

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
command -v curl >/dev/null 2>&1 || { echo "Error: curl is not installed."; exit 1; }

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

# Ensure the k8s manifests directory has all required files
echo "Verifying Kubernetes manifests..."
if [ ! -d "$SAMPLE_APP_DIR/k8s/manifests" ]; then
  echo "Error: Kubernetes manifests directory not found at $SAMPLE_APP_DIR/k8s/manifests"
  exit 1
fi

# Check for essential Kubernetes resources
ESSENTIAL_MANIFESTS=("deployment.yaml" "service.yaml" "ingress.yaml" "configmap.yaml")
for MANIFEST in "${ESSENTIAL_MANIFESTS[@]}"; do
  if [ ! -f "$SAMPLE_APP_DIR/k8s/manifests/$MANIFEST" ]; then
    echo "Error: Essential Kubernetes manifest not found: $MANIFEST"
    exit 1
  fi
done

# Create a modified manifest with the correct ECR path
echo "Updating manifest with ECR path..."
cd "$REPO_ROOT"
cp "$MANIFEST_FILE" "$MANIFEST_TEMP"

# Add k8s_path to the manifest to ensure buildandburn finds the K8s resources
# Use a hardcoded relative path rather than calculating it, which is more reliable
K8S_PATH_RELATIVE="sample-app/k8s/manifests"
K8S_PATH_ABSOLUTE="$SAMPLE_APP_DIR/k8s/manifests"

# Verify that the k8s directory exists
if [ ! -d "$K8S_PATH_ABSOLUTE" ]; then
  echo "Error: Kubernetes resources directory not found at $K8S_PATH_ABSOLUTE"
  exit 1
fi

# Update the image path in the manifest using sed and add k8s_path
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS version of sed requires different syntax
  sed -i '' "s|image:.*$IMAGE_NAME:.*|image: $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" "$MANIFEST_TEMP"
  
  # Add k8s_path if not already present - macOS version
  if ! grep -q "k8s_path:" "$MANIFEST_TEMP"; then
    # Create a temporary file with the k8s_path line
    echo "k8s_path: $K8S_PATH_RELATIVE" > /tmp/k8s_path_line.txt
    # Concatenate the temporary file with the manifest
    cat /tmp/k8s_path_line.txt "$MANIFEST_TEMP" > /tmp/new_manifest.txt
    # Replace the original manifest with the new one
    mv /tmp/new_manifest.txt "$MANIFEST_TEMP"
    # Clean up
    rm -f /tmp/k8s_path_line.txt
  fi
else
  # Linux version of sed
  sed -i "s|image:.*$IMAGE_NAME:.*|image: $ECR_REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" "$MANIFEST_TEMP"
  
  # Add k8s_path if not already present - Linux version
  if ! grep -q "k8s_path:" "$MANIFEST_TEMP"; then
    sed -i "1i k8s_path: $K8S_PATH_RELATIVE" "$MANIFEST_TEMP"
  fi
fi

echo "Using modified manifest: $MANIFEST_TEMP"
echo "K8s resources will be loaded from: $K8S_PATH_ABSOLUTE"

# Deploy infrastructure and application using BuildAndBurn
echo "Deploying infrastructure and application with BuildAndBurn..."
python3 -m cli.buildandburn up --manifest "$MANIFEST_TEMP" --env-id "$ENV_ID" --auto-approve

# Set environment variables for resource validation
PROJECT_NAME=$(grep "^name:" "$MANIFEST_TEMP" | awk '{print $2}')
K8S_NAMESPACE="bb-$PROJECT_NAME"
KUBECONFIG_PATH="/Users/alokkulkarni/.buildandburn/${ENV_ID}/kubeconfig"

# Verify the kubeconfig exists
if [ ! -f "$KUBECONFIG_PATH" ]; then
  echo "Error: Kubeconfig not found at $KUBECONFIG_PATH"
  exit 1
fi

echo "========================================================"
echo "Verifying deployed resources..."
echo "========================================================"

# Wait for the ingress controller to be ready
echo "Waiting for the NGINX ingress controller to be ready..."
INGRESS_CONTROLLER_URL=""
ATTEMPT=0
MAX_ATTEMPTS=30
WAIT_TIME=10

until [ $ATTEMPT -ge $MAX_ATTEMPTS ]
do
  INGRESS_CONTROLLER_URL=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
  
  if [ -n "$INGRESS_CONTROLLER_URL" ]; then
    echo "✅ NGINX ingress controller is ready: $INGRESS_CONTROLLER_URL"
    break
  fi
  
  ATTEMPT=$((ATTEMPT+1))
  echo "Waiting for ingress controller... Attempt $ATTEMPT/$MAX_ATTEMPTS"
  sleep $WAIT_TIME
done

if [ -z "$INGRESS_CONTROLLER_URL" ]; then
  echo "❌ Failed to get ingress controller URL after $MAX_ATTEMPTS attempts"
  exit 1
fi

# Verify the Kubernetes resources
echo "Verifying Kubernetes resources in namespace: $K8S_NAMESPACE"

# Check if the namespace exists
if ! KUBECONFIG=$KUBECONFIG_PATH kubectl get namespace $K8S_NAMESPACE > /dev/null 2>&1; then
  echo "❌ Namespace $K8S_NAMESPACE does not exist. Deployment may have failed."
  exit 1
fi

# Check if the ConfigMap and Secret exist
echo "Checking for ConfigMap and Secret..."
if ! KUBECONFIG=$KUBECONFIG_PATH kubectl get configmap postgres-app-config -n $K8S_NAMESPACE > /dev/null 2>&1; then
  echo "❌ ConfigMap 'postgres-app-config' not found in namespace $K8S_NAMESPACE"
  # Let's create it from the manifest
  echo "Applying ConfigMap manifest..."
  
  # Update the ConfigMap to use the actual RDS endpoint
  DB_ENDPOINT=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get cm -n $K8S_NAMESPACE postgres-app-config -o jsonpath='{.data.DB_HOST}' 2>/dev/null)
  if [ -z "$DB_ENDPOINT" ]; then
    # Get DB endpoint from Terraform outputs
    DB_ENDPOINT=$(python3 -m cli.buildandburn info --env-id "$ENV_ID" | grep "Database endpoint" | awk -F': ' '{print $2}')
    
    echo "Updating ConfigMap with RDS endpoint: $DB_ENDPOINT"
    # Create a temporary ConfigMap file with the correct DB endpoint
    cp "$K8S_PATH_ABSOLUTE/configmap.yaml" /tmp/configmap-updated.yaml
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
      # macOS version of sed
      sed -i '' "s|DB_HOST:.*|DB_HOST: \"$DB_ENDPOINT\"|g" /tmp/configmap-updated.yaml
    else
      # Linux version of sed
      sed -i "s|DB_HOST:.*|DB_HOST: \"$DB_ENDPOINT\"|g" /tmp/configmap-updated.yaml
    fi
    
    # Apply the updated ConfigMap
    KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f /tmp/configmap-updated.yaml -n $K8S_NAMESPACE
    rm -f /tmp/configmap-updated.yaml
  else 
    KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f "$K8S_PATH_ABSOLUTE/configmap.yaml" -n $K8S_NAMESPACE
  fi
fi

if ! KUBECONFIG=$KUBECONFIG_PATH kubectl get secret postgres-app-secret -n $K8S_NAMESPACE > /dev/null 2>&1; then
  echo "❌ Secret 'postgres-app-secret' not found in namespace $K8S_NAMESPACE"
  # Let's create it with the RDS password from Terraform outputs
  
  # Get the password from buildandburn info (note: this is sensitive info and should be handled carefully)
  DB_PASSWORD=$(python3 -m cli.buildandburn info --env-id "$ENV_ID" --detailed | grep "Database password" | awk -F': ' '{print $2}')
  
  if [ -z "$DB_PASSWORD" ]; then
    # If we can't get the password, use a default for testing
    DB_PASSWORD="postgres-password"
    echo "⚠️ Using default database password for testing"
  else
    echo "✅ Retrieved database password from Terraform outputs"
  fi
  
  # Create the Secret with the correct password
  echo "Creating Secret with database password..."
  echo -n "$DB_PASSWORD" | KUBECONFIG=$KUBECONFIG_PATH kubectl create secret generic postgres-app-secret \
    --from-file=DB_PASSWORD=/dev/stdin \
    -n $K8S_NAMESPACE
fi

# Manually apply all the manifests to ensure they're deployed
echo "Applying all Kubernetes manifests..."
for manifest in "${ESSENTIAL_MANIFESTS[@]}"; do
  echo "Applying $manifest..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f "$K8S_PATH_ABSOLUTE/$manifest" -n $K8S_NAMESPACE
done

# Wait for the deployment to become ready
echo "Waiting for deployment to be ready..."
if ! wait_for_resource "deployment" "postgres-app" "$K8S_NAMESPACE" $MAX_WAIT "$KUBECONFIG_PATH"; then
  echo "❌ Deployment 'postgres-app' failed to become ready within $MAX_WAIT seconds"
  echo "Checking pod status..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $K8S_NAMESPACE
  KUBECONFIG=$KUBECONFIG_PATH kubectl describe deployment postgres-app -n $K8S_NAMESPACE
  # Continue anyway to get more diagnostic information
fi

# Wait for the service to be ready
echo "Waiting for service to be ready..."
if ! wait_for_resource "service" "postgres-app" "$K8S_NAMESPACE" $MAX_WAIT "$KUBECONFIG_PATH"; then
  echo "❌ Service 'postgres-app' failed to become ready within $MAX_WAIT seconds"
  echo "Checking service status..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl get svc -n $K8S_NAMESPACE
  KUBECONFIG=$KUBECONFIG_PATH kubectl describe service postgres-app -n $K8S_NAMESPACE
  # Continue anyway to get more diagnostic information
fi

# Wait for the ingress to be ready
echo "Waiting for ingress to be ready..."
if ! wait_for_resource "ingress" "postgres-app" "$K8S_NAMESPACE" $MAX_WAIT "$KUBECONFIG_PATH"; then
  echo "❌ Ingress 'postgres-app' failed to become ready within $MAX_WAIT seconds"
  echo "Checking ingress status..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl get ingress -n $K8S_NAMESPACE
  KUBECONFIG=$KUBECONFIG_PATH kubectl describe ingress postgres-app -n $K8S_NAMESPACE
  # Continue anyway to get more diagnostic information
fi

# Show the status of all resources
echo "========================================================"
echo "Current status of deployed resources:"
echo "========================================================"
echo "Pods:"
KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $K8S_NAMESPACE -o wide
echo ""
echo "Services:"
KUBECONFIG=$KUBECONFIG_PATH kubectl get svc -n $K8S_NAMESPACE -o wide
echo ""
echo "Ingresses:"
KUBECONFIG=$KUBECONFIG_PATH kubectl get ingress -n $K8S_NAMESPACE -o wide
echo ""

# Show deployment information from buildandburn
echo "========================================================"
echo "Retrieving deployment information..."
echo "========================================================"
python3 -m cli.buildandburn info --env-id "$ENV_ID" --detailed

# Test the deployed application
echo "========================================================"
echo "Testing the deployed application..."
echo "========================================================"

# Get the application URL (use ingress controller URL as a fallback)
APP_URL="http://$INGRESS_CONTROLLER_URL"
APP_HOSTNAME=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get ingress postgres-app -n $K8S_NAMESPACE -o jsonpath='{.spec.rules[0].host}' 2>/dev/null)

if [ -n "$APP_HOSTNAME" ]; then
  echo "Using ingress hostname: $APP_HOSTNAME"
  # For testing without DNS, we can use the Host header with the actual ingress controller URL
  echo "Testing with host header..."
  # Test application with Host header
  if test_application "$APP_URL" "$APP_HOSTNAME"; then
    echo "✅ Application tests passed!"
  else
    echo "❌ Application tests failed. The deployment may not be fully functional."
  fi
else
  echo "Using ingress controller URL directly: $APP_URL"
  # Test application directly
  if test_application "$APP_URL"; then
    echo "✅ Application tests passed!"
  else
    echo "❌ Application tests failed. The deployment may not be fully functional."
  fi
fi

echo "========================================================"
echo "DEPLOYMENT COMPLETE!"
echo "Environment ID: $ENV_ID"
echo ""
echo "Ingress Controller URL: http://$INGRESS_CONTROLLER_URL"
echo ""
echo "To access the application:"
echo "1. For testing: curl -H 'Host: $APP_HOSTNAME' $APP_URL/health"
echo "2. For production: Set up DNS to point $APP_HOSTNAME to $INGRESS_CONTROLLER_URL"
echo ""
echo "To monitor the application:"
echo "KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $K8S_NAMESPACE"
echo "KUBECONFIG=$KUBECONFIG_PATH kubectl logs -n $K8S_NAMESPACE deployment/postgres-app"
echo ""
echo "To clean up all resources when finished:"
echo "python3 -m cli.buildandburn down --env-id $ENV_ID --auto-approve"
echo "========================================================"

# Clean up temporary manifest
rm -f "$MANIFEST_TEMP" 