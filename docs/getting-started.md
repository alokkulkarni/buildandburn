# Getting Started with Build and Burn

This guide will help you get started with creating your first disposable development environment using the Build and Burn CLI tool.

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Python 3.7+**
2. **AWS CLI**: Configured with appropriate credentials
3. **Terraform**: Version 1.0.0 or later
4. **kubectl**: For interacting with Kubernetes clusters
5. **Helm**: For deploying applications to Kubernetes

## Installation

Install the Build and Burn CLI using pip:

```bash
pip install buildandburn
```

Or install from source:

```bash
git clone https://github.com/yourusername/buildandburn.git
cd buildandburn/cli
pip install -e .
```

## Creating Your First Environment

### 1. Create a Manifest File

The first step is to create a manifest file that defines your environment. Create a file named `my-app.yaml` with the following content:

```yaml
name: my-app
region: eu-west-2

# Services to deploy
services:
  - name: backend
    image: nginx:alpine
    port: 80
    replicas: 1
    expose: true

# Optional infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
```

This manifest defines a simple application with an Nginx backend service and a PostgreSQL database.

### 2. Create the Environment

Run the following command to create your environment:

```bash
buildandburn up --manifest my-app.yaml
```

The tool will:
1. Provision the necessary AWS infrastructure
2. Create a Kubernetes cluster
3. Deploy your services
4. Display access information when complete

For a dry run that validates your configuration without creating resources:

```bash
buildandburn up --manifest my-app.yaml --dry-run
```

### 3. Access Your Environment

Once the environment is created, the CLI will display access information for your services. You can also get this information at any time using:

```bash
buildandburn info --env-id <env_id>
```

Replace `<env_id>` with the ID that was generated when you created the environment.

### 4. List All Environments

To see a list of all your environments, run:

```bash
buildandburn list
```

### 5. Destroy the Environment

When you're done with the environment, you can destroy it to free up resources:

```bash
buildandburn down --env-id <env_id>
```

This will destroy all the infrastructure created for the environment.

## Using Custom Kubernetes Resources

You can provide your own Kubernetes resources instead of having Build and Burn generate them automatically.

### 1. Create Custom Kubernetes Resources

Create a directory for your Kubernetes resources:

```bash
mkdir -p custom-k8s/my-app/templates
```

Add your Kubernetes manifests or Helm chart files to this directory.

### 2. Reference the Custom Resources in Your Manifest

Update your manifest file to reference the custom resources:

```yaml
name: my-app-custom
region: eu-west-2
k8s_path: './custom-k8s/my-app'  # Path to your custom K8s resources

services:
  - name: backend
    image: nginx:alpine
    port: 80
```

### 3. Create the Environment with Custom Resources

Use the `--no-generate-k8s` flag to tell Build and Burn to use your custom resources:

```bash
buildandburn up --manifest my-app-custom.yaml --no-generate-k8s
```

## Advanced Manifest Examples

### Multiple Services

```yaml
name: multi-service-app
region: eu-west-2

services:
  - name: backend
    image: my-backend:latest
    port: 8080
    replicas: 2
    expose: true
  
  - name: frontend
    image: my-frontend:latest
    port: 80
    replicas: 1
    expose: true

dependencies:
  - type: database
    provider: postgres
    version: "13"
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
```

### Custom Configuration

You can add custom configuration to your services:

```yaml
services:
  - name: backend
    image: my-backend:latest
    port: 8080
    configMapData:
      application.properties: |
        server.port=8080
        spring.datasource.url=jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}
        spring.datasource.username=${DB_USER}
        spring.datasource.password=${DB_PASSWORD}
    volumeMounts:
      - name: config-volume
        mountPath: /app/config/application.properties
        subPath: application.properties
    volumes:
      - name: config-volume
        configMap:
          name: backend-config
          items:
            - key: application.properties
              path: application.properties
```

## GitHub Actions Integration

You can also use Build and Burn with GitHub Actions. See [GitHub Actions Integration](./auto-deploy.md) for details.

## Next Steps

- See the [Manifest Reference](./manifest-reference.md) for detailed information about the manifest file format.
- Check out the [CLI Reference](./cli-reference.md) for more information about the CLI commands.
- Learn how to [integrate with your IDE](./ide-plugins/README.md).
- Explore [Backstage integration](./backstage/README.md) for portal-based environment management. 