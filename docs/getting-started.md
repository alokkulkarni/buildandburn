# Getting Started with Build and Burn

This guide will help you get started with creating your first disposable development environment using the Build and Burn CLI tool.

## Prerequisites

Before you begin, make sure you have installed the Build and Burn CLI tool and configured your AWS credentials. See the [Installation Guide](../INSTALL.md) for details.

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
buildandburn up my-app.yaml
```

The tool will provision the necessary AWS infrastructure, create a Kubernetes cluster, and deploy your services.

### 3. Access Your Environment

Once the environment is created, the CLI will display access information for your services. You can also get this information at any time using:

```bash
buildandburn info <env_id>
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
buildandburn down <env_id>
```

This will destroy all the infrastructure created for the environment.

## Using Custom Manifests

You can customize your environment by modifying the manifest file. Here are some examples:

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

## Next Steps

- See the [Manifest Reference](./manifest-reference.md) for detailed information about the manifest file format.
- Check out the [CLI Reference](./cli-reference.md) for more information about the CLI commands.
- Learn how to [integrate with your IDE](./ide-integration.md). 