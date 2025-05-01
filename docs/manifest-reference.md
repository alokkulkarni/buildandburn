# Manifest Reference

The Build and Burn CLI tool uses a YAML manifest file to define the environment structure. This document provides a reference for all the available fields in the manifest file.

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The name of the environment. Used for identification and for generating resource names. |
| `region` | string | Yes | The AWS region to deploy resources to (e.g., `eu-west-2`). |
| `services` | array | Yes | An array of service definitions to deploy (see Service Fields). |
| `dependencies` | array | No | An array of infrastructure dependency definitions (see Dependency Fields). |

Example:

```yaml
name: my-app
region: eu-west-2
services:
  - name: frontend
    image: nginx:alpine
dependencies:
  - type: database
    provider: postgres
```

## Service Fields

Each service in the `services` array can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The name of the service. |
| `image` | string | Yes | The Docker image to use for the service. |
| `port` | integer | No | The port the service listens on. Default: `8080`. |
| `replicas` | integer | No | The number of replicas to deploy. Default: `1`. |
| `expose` | boolean | No | Whether to expose the service via an ingress. Default: `true`. |
| `configMapData` | object | No | Key-value pairs for configuration data to be added to a ConfigMap. |
| `volumeMounts` | array | No | Array of volume mounts for the container (see Volume Mount Fields). |
| `volumes` | array | No | Array of volume definitions for the pod (see Volume Fields). |
| `env` | array | No | Array of environment variables (see Environment Variable Fields). |
| `resources` | object | No | Resource requests and limits (see Resource Fields). |

Example:

```yaml
services:
  - name: backend
    image: my-backend:latest
    port: 8080
    replicas: 2
    expose: true
    configMapData:
      application.properties: |
        server.port=8080
        logging.level.root=INFO
```

## Volume Mount Fields

Each volume mount in the `volumeMounts` array can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The name of the volume to mount. |
| `mountPath` | string | Yes | The path within the container to mount the volume at. |
| `subPath` | string | No | The subpath within the volume to mount. |
| `readOnly` | boolean | No | Whether the volume is mounted read-only. Default: `false`. |

## Volume Fields

Each volume in the `volumes` array can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The name of the volume. |
| `configMap` | object | No | ConfigMap volume source. |
| `secret` | object | No | Secret volume source. |
| `emptyDir` | object | No | EmptyDir volume source. |
| `persistentVolumeClaim` | object | No | PersistentVolumeClaim volume source. |

## Environment Variable Fields

Each environment variable in the `env` array can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The name of the environment variable. |
| `value` | string | No | The value of the environment variable. |
| `valueFrom` | object | No | Source for the environment variable's value (see Value From Fields). |

## Value From Fields

The `valueFrom` object can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `configMapKeyRef` | object | No | Reference to a key in a ConfigMap. |
| `secretKeyRef` | object | No | Reference to a key in a Secret. |
| `fieldRef` | object | No | Reference to a field of the pod. |
| `resourceFieldRef` | object | No | Reference to a container's resource request or limit. |

## Resource Fields

The `resources` object can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `requests` | object | No | Resource requests for the container. |
| `limits` | object | No | Resource limits for the container. |

## Dependency Fields

Each dependency in the `dependencies` array can have the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | The type of dependency. Can be `database` or `queue`. |
| `provider` | string | No | The provider for the dependency. For databases, can be `postgres`, `mysql`, or `mariadb`. For queues, can be `rabbitmq`. |
| `version` | string | No | The version of the dependency. |
| `storage` | integer | No | For databases, the allocated storage in GB. Default: `20`. |
| `instance_class` | string | No | The instance class to use. Default for databases: `db.t3.small`. Default for queues: `mq.t3.micro`. |

Example:

```yaml
dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
  
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
    instance_class: mq.t3.micro
```

## Complete Example

Here's a complete example of a manifest file with multiple services and dependencies:

```yaml
name: full-stack-app
region: eu-west-2

services:
  - name: backend
    image: myorg/backend:latest
    port: 8080
    replicas: 2
    expose: true
    configMapData:
      application.properties: |
        server.port=8080
        spring.datasource.url=jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}
        spring.datasource.username=${DB_USER}
        spring.datasource.password=${DB_PASSWORD}
        spring.rabbitmq.host=${RABBITMQ_HOST}
        spring.rabbitmq.port=${RABBITMQ_PORT}
        spring.rabbitmq.username=${RABBITMQ_USER}
        spring.rabbitmq.password=${RABBITMQ_PASSWORD}
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
    resources:
      requests:
        cpu: "200m"
        memory: "512Mi"
      limits:
        cpu: "500m"
        memory: "1Gi"
  
  - name: frontend
    image: myorg/frontend:latest
    port: 80
    replicas: 1
    expose: true
    env:
      - name: BACKEND_URL
        value: http://backend:8080
    resources:
      requests:
        cpu: "100m"
        memory: "256Mi"
      limits:
        cpu: "200m"
        memory: "512Mi"

dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
  
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
    instance_class: mq.t3.micro
``` 