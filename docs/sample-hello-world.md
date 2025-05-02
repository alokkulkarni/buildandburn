# Hello World Sample Deployment

This document explains how to deploy a simple Hello World application using the Build and Burn framework. This sample deploys a Spring Boot backend and an Nginx frontend that proxies requests to the backend.

## Sample Manifest

The sample manifest defines:

1. A Spring Boot backend container that serves a simple "Hello World" response
2. An Nginx frontend that proxies requests to the backend
3. Optional infrastructure dependencies (PostgreSQL database and RabbitMQ message queue)

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
    service:
      type: LoadBalancer  # Make the service externally accessible
  
  - name: nginx-frontend
    image: nginx:alpine
    port: 80
    replicas: 1
    expose: true
    service:
      type: LoadBalancer  # Make the service externally accessible
    configMapData:
      nginx.conf: |
        server {
            listen 80;
            server_name localhost;
            
            location / {
                proxy_pass http://springboot-backend:8080;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
    # Nginx configuration is mounted as a volume
    volumeMounts:
      - name: nginx-config
        mountPath: /etc/nginx/conf.d/default.conf
        subPath: nginx.conf
    volumes:
      - name: nginx-config
        configMap:
          name: nginx-frontend-config
          items:
            - key: nginx.conf
              path: nginx.conf

# Optional infrastructure dependencies
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

## How It Works

1. The Spring Boot backend container runs a simple web service that returns "Hello World" when accessed
2. The Nginx frontend container is configured to proxy all requests to the backend service
3. Both services are exposed via LoadBalancer services, making them directly accessible from outside the cluster
4. The Nginx configuration is provided as a ConfigMap and mounted into the container

## Deployment

To deploy this sample, run:

```bash
buildandburn up --manifest sample-manifest.yaml
```

This will:
1. Provision the infrastructure using Terraform
2. Deploy the Kubernetes resources
3. Configure networking and service discovery

## Testing the Deployment

Once deployed, the CLI will output access information for your services. You can access:

1. The frontend service at the provided LoadBalancer URL/IP
2. The backend service directly at its LoadBalancer URL/IP

Both should display "Hello World" when accessed, but the frontend request will be proxied through Nginx to the Spring Boot backend.

You can retrieve these URLs at any time using:

```bash
buildandburn info --env-id <env-id>
```

## Customization

You can modify this sample by:

1. Changing the Spring Boot image to your own application
2. Adjusting the Nginx configuration for more complex routing
3. Adding environment variables to connect to the database or message queue
4. Scaling the number of replicas for higher availability

## Cleanup

To destroy the environment when you're done:

```bash
buildandburn down --env-id <env-id>
```

This will destroy all resources created by the deployment, including the Kubernetes cluster, networking components, and any infrastructure dependencies. 