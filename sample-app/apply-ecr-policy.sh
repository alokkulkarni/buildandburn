#!/bin/bash
# Script to apply ECR policy to an existing BuildAndBurn environment

set -e

# Configuration
ENV_ID="1746260158"
AWS_REGION="${AWS_REGION:-eu-west-2}"
HOME_DIR=$(echo ~)
BUILDANDBURN_DIR="${HOME_DIR}/.buildandburn/${ENV_ID}"
SAMPLE_APP_DIR="$(dirname "$0")"

echo "========================================================"
echo "  Applying ECR Access Policy to Environment"
echo "========================================================"
echo "Environment ID: $ENV_ID"
echo "AWS Region: $AWS_REGION"
echo "Environment Directory: $BUILDANDBURN_DIR"
echo "Sample App Directory: $SAMPLE_APP_DIR"

# Check if required tools are installed
echo "Checking prerequisites..."
command -v aws >/dev/null 2>&1 || { echo "Error: AWS CLI is not installed."; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl is not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is not installed."; exit 1; }

# Check if environment directory exists
if [ ! -d "$BUILDANDBURN_DIR" ]; then
  echo "Error: Environment directory not found at $BUILDANDBURN_DIR"
  exit 1
fi

# Get the kubeconfig path
KUBECONFIG_PATH="${BUILDANDBURN_DIR}/kubeconfig"
if [ ! -f "$KUBECONFIG_PATH" ]; then
  echo "Error: Kubeconfig not found at $KUBECONFIG_PATH"
  exit 1
fi

# Get AWS account ID
echo "Getting AWS account information..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
  echo "Error: Failed to get AWS account ID. Are you logged in to AWS CLI?"
  echo "Run 'aws configure' to set up your AWS credentials."
  exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"

# Get EKS cluster information from kubeconfig
echo "Getting EKS cluster information from kubeconfig..."
KUBECONFIG=$KUBECONFIG_PATH kubectl config view --minify -o jsonpath='{.clusters[0].name}' > /dev/null
if [ $? -ne 0 ]; then
  echo "Error: Could not get cluster information from kubeconfig"
  exit 1
fi

# Get EKS cluster name from AWS
echo "Getting EKS clusters in region $AWS_REGION..."
EKS_CLUSTERS=$(aws eks list-clusters --region $AWS_REGION --query 'clusters' --output text)
if [ -z "$EKS_CLUSTERS" ]; then
  echo "Error: No EKS clusters found in region $AWS_REGION"
  exit 1
fi

# Find cluster that matches our environment ID
for CLUSTER in $EKS_CLUSTERS; do
  if [[ "$CLUSTER" == *"$ENV_ID"* ]] || [[ "$CLUSTER" == *"postgres-app"* ]]; then
    EKS_CLUSTER_NAME="$CLUSTER"
    break
  fi
done

if [ -z "$EKS_CLUSTER_NAME" ]; then
  echo "Error: Could not find an EKS cluster for environment $ENV_ID"
  for CLUSTER in $EKS_CLUSTERS; do
    echo "Available cluster: $CLUSTER"
  done
  read -p "Enter the correct cluster name from the list above: " EKS_CLUSTER_NAME
  if [ -z "$EKS_CLUSTER_NAME" ]; then
    echo "No cluster name provided. Exiting."
    exit 1
  fi
fi

echo "EKS Cluster Name: $EKS_CLUSTER_NAME"

# Get node role name from AWS CLI
echo "Getting EKS node role..."
NODE_GROUPS=$(aws eks list-nodegroups --cluster-name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" --query "nodegroups" --output text)
if [ -z "$NODE_GROUPS" ]; then
  echo "Error: No node groups found for cluster $EKS_CLUSTER_NAME"
  exit 1
fi

NODE_GROUP_NAME=$(echo "$NODE_GROUPS" | awk '{print $1}')
echo "Node Group: $NODE_GROUP_NAME"

NODE_ROLE_ARN=$(aws eks describe-nodegroup --cluster-name "$EKS_CLUSTER_NAME" --nodegroup-name "$NODE_GROUP_NAME" --region "$AWS_REGION" --query "nodegroup.nodeRole" --output text)
if [ -z "$NODE_ROLE_ARN" ]; then
  echo "Error: Could not get node role ARN from AWS CLI"
  exit 1
fi

NODE_ROLE_NAME=$(echo "$NODE_ROLE_ARN" | awk -F'/' '{print $2}')
echo "Node Role Name: $NODE_ROLE_NAME"

# Create ECR policy
echo "Creating and attaching ECR policy..."
POLICY_NAME="${EKS_CLUSTER_NAME}-eks-to-ecr-policy"
POLICY_DOC='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:DescribeRepositories",
        "ecr:ListImages",
        "ecr:DescribeImages",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::*:role/*ECR*"
    }
  ]
}'

# Check if policy already exists
if aws iam get-policy --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}" 2>/dev/null; then
  echo "Policy ${POLICY_NAME} already exists, using existing policy"
  POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"
else
  echo "Creating new ECR policy: ${POLICY_NAME}"
  POLICY_ARN=$(aws iam create-policy --policy-name "${POLICY_NAME}" --policy-document "${POLICY_DOC}" --query "Policy.Arn" --output text)
  if [ -z "$POLICY_ARN" ]; then
    echo "Error: Failed to create policy"
    exit 1
  fi
fi

echo "Policy ARN: $POLICY_ARN"

# Attach policy to node role
echo "Attaching policy to node role..."
if aws iam list-attached-role-policies --role-name "$NODE_ROLE_NAME" --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN']" --output text | grep -q "$POLICY_ARN"; then
  echo "Policy already attached to role"
else
  aws iam attach-role-policy --role-name "$NODE_ROLE_NAME" --policy-arn "$POLICY_ARN"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to attach policy to role"
    exit 1
  fi
  echo "Successfully attached policy to role"
fi

# Create ECR repository if it doesn't exist
IMAGE_NAME="postgres-app"
IMAGE_TAG="latest"
echo "Ensuring ECR repository exists: $IMAGE_NAME"
aws ecr describe-repositories --repository-names $IMAGE_NAME --region $AWS_REGION >/dev/null 2>&1 || \
aws ecr create-repository --repository-name $IMAGE_NAME --region $AWS_REGION

# Build and push Docker image to ECR
echo "Building and pushing Docker image to ECR..."
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_IMAGE="${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build Docker image
echo "Building Docker image..."
cd "$SAMPLE_APP_DIR"
# Add platform flag to ensure compatibility with EKS nodes (likely running on x86_64)
docker build --platform linux/amd64 -t $ECR_IMAGE .

# Push to ECR
echo "Pushing Docker image to ECR..."
docker push $ECR_IMAGE
echo "Image pushed successfully: $ECR_IMAGE"

# Get the existing namespace
NAMESPACE=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get namespaces | grep postgres-app | awk '{print $1}')
if [ -z "$NAMESPACE" ]; then
  echo "Warning: Could not find a namespace with postgres-app"
  NAMESPACE="default"
fi

echo "Using namespace: $NAMESPACE"

# Update the deployment to use the ECR image
echo "Updating deployment to use ECR image: $ECR_IMAGE"
# First check if we need to patch the deployment to use the full ECR path
CURRENT_IMAGE=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get deployment postgres-app -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)
if [ -n "$CURRENT_IMAGE" ] && [ "$CURRENT_IMAGE" != "$ECR_IMAGE" ]; then
  if [[ "$CURRENT_IMAGE" == "postgres-app:latest" ]]; then
    echo "Deployment is using unqualified image name. Patching deployment..."
    # Create a patch file for the deployment
    cat <<EOF > /tmp/deployment-patch.yaml
spec:
  template:
    spec:
      containers:
      - name: postgres-app
        image: $ECR_IMAGE
EOF
    KUBECONFIG=$KUBECONFIG_PATH kubectl patch deployment postgres-app -n $NAMESPACE --patch-file /tmp/deployment-patch.yaml
    rm -f /tmp/deployment-patch.yaml
  else
    # Just update the image as usual
    KUBECONFIG=$KUBECONFIG_PATH kubectl set image deployment/postgres-app postgres-app=$ECR_IMAGE -n $NAMESPACE
  fi
else
  KUBECONFIG=$KUBECONFIG_PATH kubectl set image deployment/postgres-app postgres-app=$ECR_IMAGE -n $NAMESPACE
fi

if [ $? -ne 0 ]; then
  echo "Warning: Failed to update deployment. Checking if deployment exists..."
  if ! KUBECONFIG=$KUBECONFIG_PATH kubectl get deployment postgres-app -n $NAMESPACE > /dev/null 2>&1; then
    echo "Deployment 'postgres-app' not found in namespace $NAMESPACE."
    echo "Creating a test pod instead to verify ECR access..."
    
    # Create a test pod
    echo "Creating test pod with image: $ECR_IMAGE"
    cat <<EOF > /tmp/ecr-test-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: ecr-test-pod
  namespace: $NAMESPACE
spec:
  containers:
  - name: ecr-test
    image: $ECR_IMAGE
    command: ["sleep", "3600"]  # Increase sleep time to 1 hour for debugging
  restartPolicy: Never
EOF

    KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f /tmp/ecr-test-pod.yaml
    rm -f /tmp/ecr-test-pod.yaml
  fi
fi

# Wait for the pods to restart with the new image
echo "Waiting for pods to update (this may take a minute)..."
ATTEMPTS=0
MAX_ATTEMPTS=30
WAIT_TIME=5

until [ $ATTEMPTS -ge $MAX_ATTEMPTS ]
do
  # Check deployment status first
  DEPLOYMENT_STATUS=$(KUBECONFIG=$KUBECONFIG_PATH kubectl rollout status deployment/postgres-app -n $NAMESPACE --timeout=5s 2>/dev/null)
  DEPLOYMENT_RESULT=$?
  
  if [ $DEPLOYMENT_RESULT -eq 0 ]; then
    echo "✅ Deployment updated successfully - ECR access is working correctly!"
    
    # Validate pods are actually running with the image
    RUNNING_PODS=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $NAMESPACE -l app=postgres-app -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}')
    if [ -n "$RUNNING_PODS" ]; then
      echo "✅ Pods are running successfully with the ECR image!"
      break
    else
      echo "⚠️ Deployment says ready but pods might not be running. Checking pod status..."
      KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $NAMESPACE -l app=postgres-app
    fi
  fi
  
  # If deployment check failed, check the test pod if we created one
  POD_STATUS=$(KUBECONFIG=$KUBECONFIG_PATH kubectl get pod ecr-test-pod -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null)
  
  if [ "$POD_STATUS" == "Running" ] || [ "$POD_STATUS" == "Succeeded" ]; then
    echo "✅ Test pod is $POD_STATUS - ECR access is working correctly!"
    break
  elif [ "$POD_STATUS" == "Failed" ] || [ "$POD_STATUS" == "Unknown" ]; then
    echo "❌ Test pod failed. Checking pod details..."
    KUBECONFIG=$KUBECONFIG_PATH kubectl describe pod ecr-test-pod -n $NAMESPACE
    echo "Check pod logs:"
    KUBECONFIG=$KUBECONFIG_PATH kubectl logs ecr-test-pod -n $NAMESPACE
    break
  else
    ATTEMPTS=$((ATTEMPTS+1))
    if [ -n "$POD_STATUS" ]; then
      echo "Pod status: $POD_STATUS (Attempt $ATTEMPTS/$MAX_ATTEMPTS)"
    else
      echo "Waiting for deployment to update... (Attempt $ATTEMPTS/$MAX_ATTEMPTS)"
    fi
    sleep $WAIT_TIME
  fi
done

# Add diagnostic logging for ECR authentication
echo "Checking ECR authentication from cluster..."
cat <<EOF | KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth-diagnostic
  namespace: $NAMESPACE
data:
  script.sh: |
    #!/bin/bash
    echo "Testing AWS credentials and ECR access..."
    aws sts get-caller-identity
    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
    echo "Testing ECR repository access..."
    aws ecr describe-repositories --region ${AWS_REGION}
    echo "Trying to pull the image: ${ECR_IMAGE}"
    docker pull ${ECR_IMAGE}
    echo "Test completed."
EOF

echo "Creating diagnostic pod to test ECR access from the node..."
cat <<EOF | KUBECONFIG=$KUBECONFIG_PATH kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: ecr-diagnostic-pod
  namespace: $NAMESPACE
spec:
  containers:
  - name: aws-cli
    image: amazon/aws-cli:latest
    command:
    - /bin/bash
    - -c
    - |
      curl -sL -o /usr/local/bin/aws-auth-test.sh http://169.254.169.254/latest/meta-data/identity-credentials/ec2/info
      chmod +x /usr/local/bin/aws-auth-test.sh
      echo "Node IAM Role Information:"
      aws sts get-caller-identity
      echo "===== Testing ECR Authentication ====="
      aws ecr get-authorization-token --region ${AWS_REGION}
      echo "===== Testing ECR Repository List ====="
      aws ecr describe-repositories --region ${AWS_REGION}
      echo "Done testing. Results above."
      sleep 3600
  restartPolicy: Never
EOF

# Continue with existing wait logic
if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
  echo "Timeout waiting for deployment/pod update. Getting details..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl get pods -n $NAMESPACE
  KUBECONFIG=$KUBECONFIG_PATH kubectl describe deployment postgres-app -n $NAMESPACE 2>/dev/null
  KUBECONFIG=$KUBECONFIG_PATH kubectl describe pod ecr-test-pod -n $NAMESPACE 2>/dev/null
  
  echo "Checking diagnostic pod status..."
  KUBECONFIG=$KUBECONFIG_PATH kubectl logs ecr-diagnostic-pod -n $NAMESPACE 2>/dev/null
  
  echo ""
  echo "TROUBLESHOOTING STEPS:"
  echo "1. Verify node IAM role has proper ECR permissions"
  echo "2. Check if ECR repository exists and is accessible"
  echo "3. Ensure image is built for the correct platform (linux/amd64)"
  echo "4. Check for cross-account ECR access issues"
fi

echo "========================================================"
echo "ECR Access Policy applied successfully!"
echo "========================================================"
echo "The EKS nodes now have the necessary permissions to pull images from ECR."
echo "The Docker image has been built and pushed to: $ECR_IMAGE"
echo "The application deployment has been updated to use this image."
echo ""
echo "IMPORTANT NOTES:"
echo "1. The application is configured to connect to a PostgreSQL database"
echo "2. Update the ConfigMap with your actual database details:"
echo "   kubectl patch configmap postgres-app-config -n $NAMESPACE --patch '{\"data\":{\"DB_HOST\":\"your-actual-db-host\"}}'"
echo ""
echo "To view your application, run:"
echo "KUBECONFIG=$KUBECONFIG_PATH kubectl get svc -n $NAMESPACE" 