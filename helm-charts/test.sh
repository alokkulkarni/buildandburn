#!/bin/bash

# Set up colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   BuildAndBurn Helm Charts Test Tool   ${NC}"
echo -e "${BLUE}========================================${NC}"

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

# Check required tools
if ! command -v helm &> /dev/null; then
  log "error" "Helm is not installed. Please install Helm before continuing."
  exit 1
fi

# Test the parent chart
log "info" "Testing buildandburn-apps chart..."
PARENT_CHART="./buildandburn-apps"

# Lint the chart
log "info" "Linting charts..."
helm lint $PARENT_CHART
if [ $? -ne 0 ]; then
  log "error" "Chart linting failed"
  exit 1
fi
log "success" "Chart lint passed"

# Update dependencies
log "info" "Updating dependencies..."
helm dependency update $PARENT_CHART
if [ $? -ne 0 ]; then
  log "error" "Failed to update dependencies"
  exit 1
fi
log "success" "Dependencies updated successfully"

# Test template generation
log "info" "Testing template generation..."
helm template test-release $PARENT_CHART > /tmp/buildandburn-test-output.yaml
if [ $? -ne 0 ]; then
  log "error" "Template generation failed"
  log "info" "See details in /tmp/buildandburn-test-output.yaml"
  exit 1
fi
log "success" "Template generation successful"

# Check for essential resources
log "info" "Checking for essential resources in templates..."
grep -q "kind: Deployment" /tmp/buildandburn-test-output.yaml
if [ $? -ne 0 ]; then
  log "error" "No deployments found in template output"
  exit 1
fi

grep -q "kind: Service" /tmp/buildandburn-test-output.yaml
if [ $? -ne 0 ]; then
  log "error" "No services found in template output"
  exit 1
fi

grep -q "kind: ConfigMap" /tmp/buildandburn-test-output.yaml
if [ $? -ne 0 ]; then
  log "error" "No ConfigMaps found in template output"
  exit 1
fi

log "success" "All essential resource types found in templates"
log "success" "Chart tests completed successfully!"
log "info" "To install the chart, run: ./install.sh"

exit 0 