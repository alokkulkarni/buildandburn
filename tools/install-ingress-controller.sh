#!/bin/bash
# This script installs the NGINX Ingress Controller on an EKS cluster

set -e

KUBECONFIG=${KUBECONFIG:-~/.kube/config}
NAMESPACE=${NAMESPACE:-ingress-nginx}

echo "=== Installing NGINX Ingress Controller ==="
echo "Using KUBECONFIG: $KUBECONFIG"
echo "Installing in namespace: $NAMESPACE"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
    echo "WARNING: Helm is not installed. Falling back to kubectl-based installation."
    USE_KUBECTL=true
else
    USE_KUBECTL=false
fi

# Try to connect to the cluster
echo "Checking connection to Kubernetes cluster..."
if ! kubectl --kubeconfig="$KUBECONFIG" get nodes &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

echo "Successfully connected to Kubernetes cluster."

# Create the namespace if it doesn't exist
if ! kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &> /dev/null; then
    echo "Creating namespace: $NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG" create namespace "$NAMESPACE"
else
    echo "Namespace $NAMESPACE already exists."
fi

if [ "$USE_KUBECTL" = true ]; then
    echo "Installing NGINX Ingress Controller using kubectl..."
    
    # Apply the mandatory manifests
    echo "Applying ingress-nginx controller manifests..."
    kubectl --kubeconfig="$KUBECONFIG" apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/aws/deploy.yaml
else
    echo "Installing NGINX Ingress Controller using Helm..."
    
    # Add the ingress-nginx repository
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    
    # Install the ingress-nginx helm chart
    helm --kubeconfig="$KUBECONFIG" upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace "$NAMESPACE" \
        --set controller.service.type=LoadBalancer \
        --set controller.publishService.enabled=true
fi

echo "Waiting for ingress controller to be ready..."
kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" wait --for=condition=available --timeout=300s deployment/ingress-nginx-controller || true

echo "Getting ingress controller service details..."
kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get svc -o wide

# Get the load balancer hostname/IP
LOAD_BALANCER=$(kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
if [ -z "$LOAD_BALANCER" ]; then
    LOAD_BALANCER=$(kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
fi

if [ -n "$LOAD_BALANCER" ]; then
    echo ""
    echo "=== Ingress Controller Installed Successfully ==="
    echo "Ingress Controller LoadBalancer: $LOAD_BALANCER"
    echo ""
    echo "To use with your applications, create an Ingress resource with the 'kubernetes.io/ingress.class: nginx' annotation."
    echo "Example DNS setup:"
    echo "  1. Set up a wildcard DNS record: *.your-domain.com -> $LOAD_BALANCER"
    echo "  2. Or set up individual DNS records for your applications"
else
    echo ""
    echo "Ingress Controller installed, but LoadBalancer is still being provisioned."
    echo "Run the following command to check status:"
    echo "  kubectl --kubeconfig=\"$KUBECONFIG\" -n \"$NAMESPACE\" get svc"
fi

echo ""
echo "=== Installation Complete ===" 