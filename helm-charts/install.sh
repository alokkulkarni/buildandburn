#!/bin/bash

# Set up colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   BuildAndBurn Helm Charts Installer   ${NC}"
echo -e "${BLUE}========================================${NC}"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to log messages
log() {
  local level=$1
  local message=$2
  case $level in
    "info")
      echo -e "${BLUE}[INFO]${NC} $message"
      ;;
    "success")
      echo -e "${GREEN}[SUCCESS]${NC} $message"
      ;;
    "warning")
      echo -e "${YELLOW}[WARNING]${NC} $message"
      ;;
    "error")
      echo -e "${RED}[ERROR]${NC} $message"
      ;;
  esac
}

# Function to show usage
usage() {
  echo "Usage: $0 [OPTIONS] [RELEASE_NAME] [NAMESPACE]"
  echo ""
  echo "OPTIONS:"
  echo "  -h, --help          Show this help message"
  echo "  -d, --debug         Enable Helm debug output"
  echo "  -c, --clean         Clean up existing releases with the same name before installing"
  echo ""
  echo "ARGUMENTS:"
  echo "  RELEASE_NAME        Name for the Helm release (default: buildandburn)"
  echo "  NAMESPACE           Kubernetes namespace (default: buildandburn)"
  echo ""
  exit 1
}

# Parse arguments
DEBUG="false"
CLEAN="false"
RELEASE_NAME="buildandburn"
NAMESPACE="buildandburn"

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      usage
      ;;
    -d|--debug)
      DEBUG="true"
      shift
      ;;
    -c|--clean)
      CLEAN="true"
      shift
      ;;
    *)
      if [[ -z "$RELEASE_NAME" || "$RELEASE_NAME" == "buildandburn" ]]; then
        RELEASE_NAME="$1"
      elif [[ -z "$NAMESPACE" || "$NAMESPACE" == "buildandburn" ]]; then
        NAMESPACE="$1"
      else
        log "error" "Unknown argument: $1"
        usage
      fi
      shift
      ;;
  esac
done

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
  log "error" "Helm is not installed. Please install Helm before continuing."
  exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
  log "error" "kubectl is not installed. Please install kubectl before continuing."
  exit 1
fi

# Clean up existing release if requested
if [[ "$CLEAN" == "true" ]]; then
  log "info" "Cleaning up existing release: $RELEASE_NAME in namespace $NAMESPACE"
  helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE" 2>/dev/null || true
  kubectl delete namespace "$NAMESPACE" --wait=false 2>/dev/null || true
  
  # Wait a moment for resources to start cleaning up
  log "info" "Waiting for cleanup to begin..."
  sleep 3
fi

# Update dependencies for parent chart
log "info" "Updating Helm dependencies..."
helm dependency update ./buildandburn-apps
if [ $? -ne 0 ]; then
  log "error" "Failed to update Helm dependencies"
  exit 1
fi
log "success" "Dependencies updated successfully"

# Set debug flags if needed
DEBUG_FLAGS=""
if [ "$DEBUG" == "true" ]; then
  DEBUG_FLAGS="--debug"
  log "info" "Debug mode enabled"
fi

# Create namespace if it doesn't exist
log "info" "Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
if [ $? -ne 0 ]; then
  log "warning" "Failed to create namespace, it may already exist"
fi

# Make sure namespace is fully created before proceeding
log "info" "Waiting for namespace to be active..."
kubectl get namespace $NAMESPACE -o jsonpath='{.status.phase}' > /dev/null 2>&1
if [ $? -ne 0 ]; then
  log "error" "Failed to get namespace status"
  exit 1
fi

# Install or upgrade the Helm chart
log "info" "Installing Helm chart as release: $RELEASE_NAME"
helm upgrade --install $RELEASE_NAME ./buildandburn-apps \
  --namespace $NAMESPACE \
  --values ./buildandburn-apps/values.yaml \
  --create-namespace \
  $DEBUG_FLAGS

if [ $? -ne 0 ]; then
  log "error" "Failed to install Helm chart"
  
  # Display more information in case of failure
  log "info" "Attempting to display more information about the error..."
  helm template ./buildandburn-apps --debug > /tmp/helm-debug-output.yaml
  log "info" "Debug template generated at /tmp/helm-debug-output.yaml"
  
  exit 1
fi

log "success" "Helm chart installed successfully!"
log "info" "To access the applications, use these commands:"
log "info" "kubectl port-forward svc/$RELEASE_NAME-sb 8080:8080 -n $NAMESPACE"
log "info" "kubectl port-forward svc/$RELEASE_NAME-nf 8081:80 -n $NAMESPACE"
log "info" ""
log "info" "Then access the applications at:"
log "info" "Backend: http://localhost:8080"
log "info" "Frontend: http://localhost:8081"

exit 0 