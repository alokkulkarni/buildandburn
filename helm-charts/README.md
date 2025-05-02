# BuildAndBurn Helm Charts

This directory contains Helm charts for deploying the applications defined in the BuildAndBurn manifest file.

## Charts Structure

- `springboot-backend`: Helm chart for the Spring Boot backend application
- `nginx-frontend`: Helm chart for the Nginx frontend application
- `buildandburn-apps`: Parent chart that includes both applications

## Installation

To install the charts:

```bash
# Add the local repo
helm dependency update ./buildandburn-apps

# Install the charts
helm install myapp ./buildandburn-apps --values ./buildandburn-apps/values.yaml
```

## Configuration

The parent chart (`buildandburn-apps`) allows you to configure both applications through its `values.yaml` file. Here are the main configuration sections:

### Global Values

```yaml
global:
  domain: buildandburn.local
```

### Infrastructure Information

If you're using BuildAndBurn to provision infrastructure, these values will be populated automatically:

```yaml
infrastructure:
  database:
    enabled: true
    host: "your-db-host"
    port: 5432
    name: "your-db-name"
  rabbitmq:
    enabled: true
    host: "your-rabbitmq-host"
    port: 5672
```

### Application-Specific Configuration

Each application has its own configuration section in the parent values file. For example:

```yaml
springboot-backend:
  replicaCount: 2
  ingress:
    hosts:
      - host: api.yourdomain.com
        paths:
          - path: /
            pathType: Prefix
```

## Integration with BuildAndBurn

These Helm charts are designed to work with the BuildAndBurn infrastructure provisioning tool. When you run the BuildAndBurn CLI, it can automatically deploy these Helm charts with the correct infrastructure connection information. 