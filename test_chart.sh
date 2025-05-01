#!/bin/bash

set -e  # Exit on any error

# Configuration
MANIFEST_PATH="examples/redis-test-manifest.yaml"
OUTPUT_DIR="test_output"

# Cleanup
echo "Cleaning up previous test output..."
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Test script
echo "===== Testing Helm chart generation with Redis manifest ====="

# Generate the manifests and chart using Python
echo "Generating Kubernetes manifests and Helm chart..."
python3 -c "
import os
import sys
import yaml
import traceback

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

# Import the required modules
try:
    from cli.k8s_generator import generate_manifests, create_helm_chart
except Exception as e:
    print(f'Import error: {e}')
    traceback.print_exc()
    sys.exit(1)

# Load the manifest
try:
    with open('$MANIFEST_PATH', 'r') as f:
        manifest = yaml.safe_load(f)
    
    # Generate manifests
    manifests_dir = '$OUTPUT_DIR/manifests'
    os.makedirs(manifests_dir, exist_ok=True)
    
    print('Generating manifests...')
    manifests = generate_manifests(manifest, manifests_dir)
    if not manifests:
        print('Warning: No manifests were generated')
    else:
        print(f'Generated {len(manifests)} manifests')
    
    # Create Helm chart
    print('Creating Helm chart...')
    chart_dir = create_helm_chart(manifest, '$OUTPUT_DIR')
    print(f'Successfully generated Helm chart at {chart_dir}')
    
except Exception as e:
    print(f'Error: {str(e)}')
    traceback.print_exc()
    sys.exit(1)
"

# Test if the chart directory exists
if [ -d "$OUTPUT_DIR/chart" ]; then
    echo "✅ Chart directory created successfully"
else
    echo "❌ Chart directory not found"
    exit 1
fi

# Test Helm template rendering
echo "Testing Helm template rendering..."
if command -v helm &> /dev/null; then
    cd "$OUTPUT_DIR"
    helm template chart > rendered_templates.yaml
    
    if [ $? -eq 0 ]; then
        echo "✅ Helm template rendered successfully"
        echo "Rendered templates saved to $OUTPUT_DIR/rendered_templates.yaml"
    else
        echo "❌ Helm template rendering failed"
        exit 1
    fi
else
    echo "⚠️ Helm not found, skipping template rendering test"
fi

echo "===== Tests completed successfully! =====" 