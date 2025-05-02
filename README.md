# BuildAndBurn

BuildAndBurn is a tool for quickly creating infrastructure and deploying applications to AWS. It provisions infrastructure using Terraform and deploys applications to Kubernetes using Helm.

## Features

- One-command deployment of complete infrastructure and applications
- Support for databases (RDS), message queues (RabbitMQ), caching (ElastiCache), and Kafka
- Kubernetes deployment using EKS
- Simple manifest-based configuration

## Getting Started

1. Clone this repository
2. Install dependencies:
   - AWS CLI
   - Terraform
   - kubectl
   - Helm
3. Configure AWS credentials
4. Run the tool with a manifest file:

```bash
./cli/buildandburn.py up -f examples/test-manifest.yaml
```

## Manifest Format

The manifest file defines your infrastructure and application requirements:

```yaml
name: hello-world
region: eu-west-2

# Services to deploy
services:
  - name: springboot-backend
    image: dstar55/docker-hello-world-spring-boot:latest
    port: 8080
    replicas: 1
    expose: true
  
  - name: nginx-frontend
    image: nginx:alpine
    port: 80
    replicas: 1
    expose: true

# Infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
  
  - type: queue
    provider: RabbitMQ
    version: "3.13"
    auto_minor_version_upgrade: true
    instance_class: mq.t3.micro
```

## Components

- `cli/`: Command-line tools for infrastructure management
- `terraform/`: Terraform modules for infrastructure provisioning
- `helm-charts/`: Helm charts for application deployment
- `docs/`: Documentation
- `examples/`: Example manifest files and applications

## Helm Charts

The repository includes Helm charts for deploying applications:

- `springboot-backend`: A chart for Spring Boot applications
- `nginx-frontend`: A chart for Nginx frontend applications
- `buildandburn-apps`: A parent chart that combines multiple applications

To manually deploy the Helm charts:

```bash
cd helm-charts
./install.sh my-release my-namespace
```

## License

MIT 