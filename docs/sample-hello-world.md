# Hello World Sample Deployment

This document explains how to deploy a simple Hello World application using the Build and Burn framework. This sample deploys a Spring Boot backend and an Nginx frontend that proxies requests to the backend.

## Sample Manifest

The sample manifest (`cli/sample-manifest.yaml`) defines:

1. A Spring Boot backend container that serves a simple "Hello World" response
2. An Nginx frontend that proxies requests to the backend
3. Infrastructure dependencies (PostgreSQL database and RabbitMQ message queue)

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

# Infrastructure dependencies
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
3. Both services are exposed via Kubernetes ingress, making them accessible from outside the cluster
4. The Nginx configuration is provided as a ConfigMap and mounted into the container

## Deployment

To deploy this sample, run:

```bash
./cli/deploy_env.py cli/sample-manifest.yaml
```

This will:
1. Provision the infrastructure using Terraform
2. Deploy the Kubernetes resources
3. Configure networking and service discovery

## Testing the Deployment

Once deployed, you can access:

1. The frontend service at: `http://nginx-frontend.hello-world.<cluster-domain>/`
2. The backend service directly at: `http://springboot-backend.hello-world.<cluster-domain>/`

Both should display "Hello World" when accessed, but the frontend request will be proxied through Nginx to the Spring Boot backend.

## Customization

You can modify this sample by:

1. Changing the Spring Boot image to your own application
2. Adjusting the Nginx configuration for more complex routing
3. Adding environment variables to connect to the database or message queue
4. Scaling the number of replicas for higher availability

## Cleanup

To destroy the environment when you're done:

```bash
./cli/deploy_env.py --down cli/sample-manifest.yaml
```

Or using the main CLI:

```bash
buildandburn down --env <env-id>
``` 