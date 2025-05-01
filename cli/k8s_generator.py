#!/usr/bin/env python3
"""
Kubernetes Manifest Generator for BuildAndBurn

This tool generates Kubernetes manifest files from application specifications.
It can be used standalone or imported by the main BuildAndBurn script.
"""

import os
import sys
import yaml
import json
import argparse
import shutil
from datetime import datetime

def print_color(text, color_code):
    """Print colored text."""
    print(f"\033[{color_code}m{text}\033[0m")

def print_success(text):
    print_color(text, 92)  # Green

def print_info(text):
    print_color(text, 94)  # Blue

def print_warning(text):
    print_color(text, 93)  # Yellow

def print_error(text):
    print_color(text, 91)  # Red

def load_manifest(manifest_path):
    """Load a manifest file."""
    try:
        with open(manifest_path, 'r') as f:
            if manifest_path.endswith('.yaml') or manifest_path.endswith('.yml'):
                return yaml.safe_load(f)
            elif manifest_path.endswith('.json'):
                return json.load(f)
            else:
                raise ValueError("Unsupported manifest format. Must be YAML or JSON.")
    except Exception as e:
        print_error(f"Failed to load manifest file: {str(e)}")
        return None

def process_service_dependencies(service, service_map, namespace, manifest_dependencies=None):
    """Process service dependencies and add environment variables.
    
    Args:
        service: The service dict
        service_map: Map of all services by name
        namespace: The Kubernetes namespace
        manifest_dependencies: Dependencies configuration from manifest
    
    Returns:
        List of environment variable dicts
    """
    env_vars = []
    
    # Ensure service has env list
    if 'env' not in service:
        service['env'] = []
    
    if 'dependencies' in service:
        service_deps = service['dependencies']
        if not isinstance(service_deps, list):
            service_deps = [service_deps]
            
        for dep in service_deps:
            # Handle both string dependencies and dependency objects
            dep_name = dep if isinstance(dep, str) else dep.get('name')
            dep_type = None
            
            # Try to find dependency type from manifest_dependencies if provided
            if manifest_dependencies and not isinstance(dep, str):
                dep_type = dep.get('type')
            elif manifest_dependencies:
                # Try to find this dependency in manifest_dependencies
                for manifest_dep in manifest_dependencies:
                    if isinstance(manifest_dep, dict) and manifest_dep.get('name') == dep_name:
                        dep_type = manifest_dep.get('type')
                        break
            
            # Handle service dependencies (other k8s services)
            if dep_name in service_map:
                # Determine service port based on the dependency's configuration
                dep_service = service_map[dep_name]
                dep_port = 80  # Default port
                
                # Try to get a more specific port if possible
                if 'service' in dep_service and 'ports' in dep_service['service'] and dep_service['service']['ports']:
                    for port in dep_service['service']['ports']:
                        if isinstance(port, dict) and 'port' in port:
                            dep_port = port['port']
                            break
                elif 'ports' in dep_service and dep_service['ports']:
                    for port in dep_service['ports']:
                        if isinstance(port, dict) and 'port' in port:
                            dep_port = port['port']
                            break
                        elif isinstance(port, dict) and 'containerPort' in port:
                            dep_port = port['containerPort']
                            break
                
                # Add standard connection variables
                dep_env_prefix = dep_name.upper().replace('-', '_')
                service['env'].extend([
                    {"name": f"{dep_env_prefix}_SERVICE_HOST", "value": f"{dep_name}.{namespace}.svc.cluster.local"},
                    {"name": f"{dep_env_prefix}_SERVICE_PORT", "value": str(dep_port)}
                ])
                
                # Add additional variables based on service type
                if dep_name == 'database' or 'database' in dep_name:
                    service['env'].extend([
                        {"name": f"{dep_env_prefix}_DB_NAME", "value": "app"},  # Default DB name
                        {"name": f"{dep_env_prefix}_DB_USER", "value": "postgres"},  # Default user
                        {"name": f"{dep_env_prefix}_DB_PASSWORD", "value": "password"},  # Default password
                        {"name": f"{dep_env_prefix}_DB_URL", "value": f"postgresql://postgres:password@{dep_name}.{namespace}.svc.cluster.local:{dep_port}/app"}
                    ])
                elif dep_name == 'redis' or 'redis' in dep_name:
                    service['env'].extend([
                        {"name": f"{dep_env_prefix}_URL", "value": f"redis://{dep_name}.{namespace}.svc.cluster.local:{dep_port}"}
                    ])
                elif dep_name == 'queue' or 'mq' in dep_name or 'rabbitmq' in dep_name:
                    service['env'].extend([
                        {"name": f"{dep_env_prefix}_USER", "value": "guest"},  # Default RabbitMQ user
                        {"name": f"{dep_env_prefix}_PASSWORD", "value": "guest"},  # Default RabbitMQ password
                        {"name": f"{dep_env_prefix}_URL", "value": f"amqp://guest:guest@{dep_name}.{namespace}.svc.cluster.local:{dep_port}"}
                    ])
            
            # Handle infrastructure dependencies based on type
            elif dep_type:
                if dep_type == 'database':
                    service['env'].extend([
                        {"name": "DATABASE_HOST", "value": "${DATABASE_ENDPOINT}"},
                        {"name": "DATABASE_PORT", "value": "5432"},
                        {"name": "DATABASE_NAME", "value": "${DATABASE_NAME}"},
                        {"name": "DATABASE_USER", "value": "${DATABASE_USERNAME}"},
                        {"name": "DATABASE_PASSWORD", "value": "${DATABASE_PASSWORD}"},
                        {"name": "DATABASE_URL", "value": "postgresql://${DATABASE_USERNAME}:${DATABASE_PASSWORD}@${DATABASE_ENDPOINT}:5432/${DATABASE_NAME}"}
                    ])
                elif dep_type == 'queue':
                    service['env'].extend([
                        {"name": "RABBITMQ_HOST", "value": "${MQ_ENDPOINT}"},
                        {"name": "RABBITMQ_PORT", "value": "5672"},
                        {"name": "RABBITMQ_USER", "value": "${MQ_USERNAME}"},
                        {"name": "RABBITMQ_PASSWORD", "value": "${MQ_PASSWORD}"},
                        {"name": "RABBITMQ_URL", "value": "amqp://${MQ_USERNAME}:${MQ_PASSWORD}@${MQ_ENDPOINT}:5672/"}
                    ])
                elif dep_type == 'redis':
                    service['env'].extend([
                        {"name": "REDIS_HOST", "value": "${CACHE_ENDPOINT}"},
                        {"name": "REDIS_PORT", "value": "6379"},
                        {"name": "REDIS_URL", "value": "redis://${CACHE_ENDPOINT}:6379"}
                    ])
    
    # Add common environment variables
    service['env'].extend([
        {"name": "APP_NAME", "value": service['name']},
        {"name": "APP_NAMESPACE", "value": namespace},
        {"name": "ENV", "value": "development"}
    ])
    
    return service['env']

def generate_deployment(service, namespace, manifest=None):
    """Generate a Kubernetes Deployment resource."""
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": service['name'],
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        },
        "spec": {
            "replicas": service.get('replicas', 1),
            "selector": {
                "matchLabels": {
                    "app": service['name']
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": service['name']
                    }
                },
                "spec": {
                    "containers": [{
                        "name": service['name'],
                        "image": service['image'],
                    }]
                }
            }
        }
    }
    
    # Add command if specified
    if 'command' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["command"] = service['command']
    
    # Add args if specified
    if 'args' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["args"] = service['args']
    
    # Add container ports if specified
    if 'ports' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["ports"] = []
        for port in service['ports']:
            container_port = {
                "containerPort": port.get('containerPort', port.get('port', 8080)),
                "protocol": port.get('protocol', 'TCP')
            }
            if 'name' in port:
                container_port["name"] = port['name']
            deployment["spec"]["template"]["spec"]["containers"][0]["ports"].append(container_port)
    
    # Add resource limits and requests if specified
    if 'resources' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["resources"] = service['resources']
    
    # Add environment variables if specified
    env_vars = []
    if 'env' in service:
        env_vars.extend(service['env'])
    
    # Add environment variables from config maps and secrets
    if 'config' in service:
        # Add config map volume
        config_volume = {
            "name": f"{service['name']}-config-volume",
            "configMap": {
                "name": f"{service['name']}-config"
            }
        }
        
        # Add volume to deployment
        if "volumes" not in deployment["spec"]["template"]["spec"]:
            deployment["spec"]["template"]["spec"]["volumes"] = []
        deployment["spec"]["template"]["spec"]["volumes"].append(config_volume)
        
        # Add volume mount to container
        if "volumeMounts" not in deployment["spec"]["template"]["spec"]["containers"][0]:
            deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = []
        
        config_mount = {
            "name": f"{service['name']}-config-volume",
            "mountPath": "/etc/config"
        }
        deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(config_mount)
        
        # Add environment variable referencing config map
        env_vars.append({
            "name": "CONFIG_PATH",
            "value": "/etc/config"
        })
    
    if 'secrets' in service:
        # Option 1: Mount secrets as files
        secret_volume = {
            "name": f"{service['name']}-secret-volume",
            "secret": {
                "secretName": f"{service['name']}-secret"
            }
        }
        
        # Add volume to deployment
        if "volumes" not in deployment["spec"]["template"]["spec"]:
            deployment["spec"]["template"]["spec"]["volumes"] = []
        deployment["spec"]["template"]["spec"]["volumes"].append(secret_volume)
        
        # Add volume mount to container
        if "volumeMounts" not in deployment["spec"]["template"]["spec"]["containers"][0]:
            deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = []
        
        secret_mount = {
            "name": f"{service['name']}-secret-volume",
            "mountPath": "/etc/secrets",
            "readOnly": True
        }
        deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(secret_mount)
        
        # Add environment variable referencing secrets path
        env_vars.append({
            "name": "SECRETS_PATH",
            "value": "/etc/secrets"
        })
        
        # Option 2: Add secrets as environment variables
        for key in service['secrets']:
            env_vars.append({
                "name": key,
                "valueFrom": {
                    "secretKeyRef": {
                        "name": f"{service['name']}-secret",
                        "key": key
                    }
                }
            })
    
    # Add volume mounts if specified
    if 'volumeMounts' in service:
        if "volumeMounts" not in deployment["spec"]["template"]["spec"]["containers"][0]:
            deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = []
        deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].extend(service['volumeMounts'])
    
    # Add volumes if specified
    if 'volumes' in service:
        if "volumes" not in deployment["spec"]["template"]["spec"]:
            deployment["spec"]["template"]["spec"]["volumes"] = []
        deployment["spec"]["template"]["spec"]["volumes"].extend(service['volumes'])
    
    # Handle persistence if specified
    if 'persistence' in service and service['persistence'].get('enabled', False):
        # Volume name
        vol_name = f"{service['name']}-data"
        
        # Create volume
        volume = {
            "name": vol_name,
            "persistentVolumeClaim": {
                "claimName": vol_name
            }
        }
        
        # Add volume to deployment
        if "volumes" not in deployment["spec"]["template"]["spec"]:
            deployment["spec"]["template"]["spec"]["volumes"] = []
        deployment["spec"]["template"]["spec"]["volumes"].append(volume)
        
        # Create volume mount
        mount_path = service['persistence'].get('mountPath', '/data')
        sub_path = service['persistence'].get('subPath', '')
        
        mount = {
            "name": vol_name,
            "mountPath": mount_path
        }
        
        if sub_path:
            mount["subPath"] = sub_path
        
        # Add volume mount to container
        if "volumeMounts" not in deployment["spec"]["template"]["spec"]["containers"][0]:
            deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = []
        deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(mount)
    
    # Add readiness probe if specified
    if 'readinessProbe' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = service['readinessProbe']
    
    # Add liveness probe if specified
    if 'livenessProbe' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = service['livenessProbe']
    
    # Add startup probe if specified
    if 'startupProbe' in service:
        deployment["spec"]["template"]["spec"]["containers"][0]["startupProbe"] = service['startupProbe']
    
    # Set environment variables
    if env_vars:
        deployment["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars
    
    # Set service account if specified
    if 'serviceAccount' in service:
        deployment["spec"]["template"]["spec"]["serviceAccountName"] = service['name']
    
    # Add node selector if specified
    if 'nodeSelector' in service:
        deployment["spec"]["template"]["spec"]["nodeSelector"] = service['nodeSelector']
    
    # Add affinity if specified
    if 'affinity' in service:
        deployment["spec"]["template"]["spec"]["affinity"] = service['affinity']
    
    # Add tolerations if specified
    if 'tolerations' in service:
        deployment["spec"]["template"]["spec"]["tolerations"] = service['tolerations']
    
    return deployment

def generate_service(service, namespace):
    """Generate a Kubernetes Service resource."""
    svc = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": service['name'],
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        },
        "spec": {
            "selector": {
                "app": service['name']
            },
            "type": service.get('service', {}).get('type', 'ClusterIP'),
            "ports": []
        }
    }
    
    # Add service ports
    if 'service' in service and 'ports' in service['service']:
        svc["spec"]["ports"] = service['service']['ports']
    elif 'ports' in service:
        # Map container ports to service ports
        for port in service['ports']:
            svc_port = {
                "port": port.get('port', port.get('containerPort', 80)),
                "targetPort": port.get('containerPort', port.get('port', 8080)),
                "protocol": port.get('protocol', 'TCP')
            }
            if 'name' in port:
                svc_port["name"] = port['name']
            svc["spec"]["ports"].append(svc_port)
    else:
        # Default port
        svc["spec"]["ports"] = [{
            "port": 80,
            "targetPort": 8080,
            "protocol": "TCP"
        }]
    
    return svc

def generate_ingress(service, namespace, domain=None):
    """Generate a Kubernetes Ingress resource."""
    if not service.get('ingress', {}).get('enabled', False):
        return None
    
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": service['name'],
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            },
            "annotations": {
                "kubernetes.io/ingress.class": service.get('ingress', {}).get('className', 'nginx')
            }
        },
        "spec": {
            "rules": []
        }
    }
    
    # Add custom annotations if specified
    if 'annotations' in service.get('ingress', {}):
        ingress["metadata"]["annotations"].update(service['ingress']['annotations'])
    
    # Add TLS if specified
    if 'tls' in service.get('ingress', {}):
        ingress["spec"]["tls"] = service['ingress']['tls']
    
    # Add ingress hosts and paths
    if 'hosts' in service.get('ingress', {}):
        for host in service['ingress']['hosts']:
            rule = {
                "host": host['host'],
                "http": {
                    "paths": []
                }
            }
            
            for path in host.get('paths', [{'path': '/', 'pathType': 'Prefix'}]):
                rule["http"]["paths"].append({
                    "path": path['path'],
                    "pathType": path.get('pathType', 'Prefix'),
                    "backend": {
                        "service": {
                            "name": service['name'],
                            "port": {
                                "number": path.get('port', 80)
                            }
                        }
                    }
                })
                
            ingress["spec"]["rules"].append(rule)
    else:
        # Default rule
        host = service.get('ingress', {}).get('host')
        if not host and domain:
            host = f"{service['name']}.{domain}"
        elif not host:
            host = f"{service['name']}.example.com"
            
        ingress["spec"]["rules"].append({
            "host": host,
            "http": {
                "paths": [{
                    "path": service.get('ingress', {}).get('path', '/'),
                    "pathType": service.get('ingress', {}).get('pathType', 'Prefix'),
                    "backend": {
                        "service": {
                            "name": service['name'],
                            "port": {
                                "number": service.get('ingress', {}).get('port', 80)
                            }
                        }
                    }
                }]
            }
        })
    
    return ingress

def generate_configmap(service, namespace):
    """Generate a Kubernetes ConfigMap resource if config is specified."""
    if 'config' not in service:
        return None
    
    config_map = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{service['name']}-config",
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        },
        "data": service['config']
    }
    
    return config_map

def generate_secret(service, namespace):
    """Generate a Kubernetes Secret resource if secrets are specified."""
    if 'secrets' not in service:
        return None
    
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{service['name']}-secret",
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        },
        "type": "Opaque",
        "stringData": service['secrets']
    }
    
    return secret

def generate_persistent_volume_claim(service, namespace):
    """Generate a PVC if persistence is specified."""
    if 'persistence' not in service:
        return None
    
    pvc = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": f"{service['name']}-data",
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        },
        "spec": {
            "accessModes": service['persistence'].get('accessModes', ['ReadWriteOnce']),
            "resources": {
                "requests": {
                    "storage": service['persistence'].get('size', '1Gi')
                }
            }
        }
    }
    
    # Add storage class if specified
    if 'storageClass' in service['persistence']:
        pvc["spec"]["storageClassName"] = service['persistence']['storageClass']
    
    return pvc

def generate_service_account(service, namespace):
    """Generate a ServiceAccount if RBAC is specified."""
    if 'serviceAccount' not in service:
        return None
    
    sa = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": f"{service['name']}",
            "namespace": namespace,
            "labels": {
                "app": service['name'],
                "managed-by": "buildandburn"
            }
        }
    }
    
    return sa

def generate_manifests(manifest, output_dir=None):
    """Generate Kubernetes manifests from a Build and Burn manifest."""
    resources = []
    namespace = f"bb-{manifest['name']}"
    
    # Create namespace
    namespace_resource = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
            "labels": {
                "managed-by": "buildandburn"
            }
        }
    }
    resources.append(namespace_resource)
    
    # Process services
    if 'services' in manifest:
        service_map = {service['name']: service for service in manifest['services']}
        
        for service in manifest['services']:
            # Process dependencies to inject env vars
            if 'dependencies' in service:
                process_service_dependencies(service, service_map, namespace, manifest.get('dependencies', []))
            
            # Create Kubernetes resources for service
            deployment = generate_deployment(service, namespace, manifest)
            if deployment:
                resources.append(deployment)
            
            # Create service
            service_resource = generate_service(service, namespace)
            if service_resource:
                resources.append(service_resource)
            
            # Create ingress if needed
            # Handle both dictionary and list formats for ingress
            domain = None
            if 'ingress' in manifest:
                if isinstance(manifest['ingress'], dict):
                    domain = manifest['ingress'].get('domain')
                elif isinstance(manifest['ingress'], list):
                    # For list format, try to extract domain from the first ingress with a host
                    for ing in manifest['ingress']:
                        if 'host' in ing:
                            domain_parts = ing['host'].split('.')
                            if len(domain_parts) >= 2:
                                domain = '.'.join(domain_parts[1:])
                                break
            
            if 'ingress' in service and service['ingress'].get('enabled', False):
                ingress = generate_ingress(service, namespace, domain)
                if ingress:
                    resources.append(ingress)
            
            # Create ConfigMap if needed
            if 'config' in service:
                configmap = generate_configmap(service, namespace)
                if configmap:
                    resources.append(configmap)
            
            # Create Secret if needed
            if 'secrets' in service:
                secret = generate_secret(service, namespace)
                if secret:
                    resources.append(secret)
            
            # Create PVC if needed
            if 'persistence' in service and service['persistence'].get('enabled', False):
                pvc = generate_persistent_volume_claim(service, namespace)
                if pvc:
                    resources.append(pvc)
            
            # Create ServiceAccount
            sa = generate_service_account(service, namespace)
            if sa:
                resources.append(sa)
    
    # Generate resources for infrastructure components
    infrastructure = {}
    if 'infrastructure' in manifest:
        infrastructure = manifest['infrastructure']
    elif 'dependencies' in manifest:
        # Convert dependencies array to infrastructure object
        infrastructure = {}
        for dep in manifest['dependencies']:
            if dep['type'] == 'database':
                infrastructure['database'] = {
                    'enabled': True,
                    'engine': dep.get('provider', 'postgres'),
                    'version': dep.get('version', '13'),
                    'instance_class': dep.get('instance_class', 'db.t3.small'),
                    'storage': f"{dep.get('storage', 20)}Gi",
                    'in_cluster': True
                }
            elif dep['type'] == 'queue':
                infrastructure['message_queue'] = {
                    'enabled': True,
                    'engine': dep.get('provider', 'rabbitmq'),
                    'version': dep.get('version', '3.9'),
                    'instance_class': dep.get('instance_class', 'mq.t3.micro'),
                    'storage': '1Gi',
                    'in_cluster': True
                }
            elif dep['type'] == 'redis':
                infrastructure['cache'] = {
                    'enabled': True,
                    'engine': 'redis',
                    'version': dep.get('version', '6.2'),
                    'node_type': dep.get('node_type', 'cache.t3.micro'),
                    'cluster_size': dep.get('cluster_size', 1),
                    'storage': '1Gi',
                    'in_cluster': True
                }
                    
    infra_resources = generate_infrastructure_resources(infrastructure, namespace)
    if infra_resources:
        resources.extend(infra_resources)
    
    # Write to file if output_dir is provided
    if output_dir and resources:
        os.makedirs(output_dir, exist_ok=True)
        
        # Create combined manifest
        with open(os.path.join(output_dir, "all.yaml"), 'w') as f:
            for i, resource in enumerate(resources):
                if resource and isinstance(resource, dict) and 'kind' in resource:
                    yaml.dump(resource, f)
                    if i < len(resources) - 1:
                        f.write("---\n")
        
        # Create separate files
        for resource in resources:
            if not resource or not isinstance(resource, dict) or 'kind' not in resource or 'metadata' not in resource:
                continue
                
            kind = resource['kind'].lower()
            name = resource['metadata']['name'].lower()
            
            # Create directory for kind if multiple resources of same kind
            if kind in ["deployment", "service", "job", "cronjob"]:
                kind_dir = os.path.join(output_dir, f"{kind}s")
                os.makedirs(kind_dir, exist_ok=True)
                file_path = os.path.join(kind_dir, f"{name}.yaml")
            else:
                file_path = os.path.join(output_dir, f"{kind}.yaml")
            
            with open(file_path, 'w') as f:
                yaml.dump(resource, f)
    
    return resources

def generate_infrastructure_resources(infrastructure, namespace):
    """Generate resources for infrastructure components like databases and message queues.
    
    Args:
        infrastructure: The infrastructure configuration from manifest
        namespace: The Kubernetes namespace
        
    Returns:
        List of Kubernetes resource dicts
    """
    if not infrastructure:
        return []
        
    resources = []
    
    # Handle database
    if 'database' in infrastructure and infrastructure['database'].get('enabled', False) and infrastructure['database'].get('in_cluster', False):
        db_engine = infrastructure['database'].get('engine', 'postgres')
        
        if db_engine == 'postgres':
            # Create PostgreSQL deployment
            db_deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "database",
                    "namespace": namespace,
                    "labels": {
                        "app": "database",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {
                        "matchLabels": {
                            "app": "database"
                        }
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "app": "database"
                            }
                        },
                        "spec": {
                            "containers": [{
                                "name": "postgres",
                                "image": f"postgres:{infrastructure['database'].get('version', 'latest')}",
                                "ports": [{"containerPort": 5432}],
                                "env": [
                                    {"name": "POSTGRES_DB", "value": "app"},
                                    {"name": "POSTGRES_USER", "value": "postgres"},
                                    {"name": "POSTGRES_PASSWORD", "value": "password"}
                                ],
                                "volumeMounts": [{
                                    "name": "postgres-data",
                                    "mountPath": "/var/lib/postgresql/data"
                                }]
                            }],
                            "volumes": [{
                                "name": "postgres-data",
                                "persistentVolumeClaim": {
                                    "claimName": "postgres-data-claim"
                                }
                            }]
                        }
                    }
                }
            }
            resources.append(db_deployment)
            
            # Create PostgreSQL service
            db_service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "database",
                    "namespace": namespace,
                    "labels": {
                        "app": "database",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "selector": {
                        "app": "database"
                    },
                    "ports": [{
                        "port": 5432,
                        "targetPort": 5432
                    }]
                }
            }
            resources.append(db_service)
            
            # Create PVC for PostgreSQL
            db_pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": "postgres-data-claim",
                    "namespace": namespace,
                    "labels": {
                        "app": "database",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {
                        "requests": {
                            "storage": infrastructure['database'].get('storage', '20Gi')
                        }
                    }
                }
            }
            resources.append(db_pvc)
    
    # Handle message queue
    if 'message_queue' in infrastructure and infrastructure['message_queue'].get('enabled', False) and infrastructure['message_queue'].get('in_cluster', False):
        mq_engine = infrastructure['message_queue'].get('engine', 'rabbitmq')
        
        if mq_engine == 'rabbitmq':
            # Create RabbitMQ deployment
            mq_deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "queue",
                    "namespace": namespace,
                    "labels": {
                        "app": "queue",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {
                        "matchLabels": {
                            "app": "queue"
                        }
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "app": "queue"
                            }
                        },
                        "spec": {
                            "containers": [{
                                "name": "rabbitmq",
                                "image": f"rabbitmq:{infrastructure['message_queue'].get('version', 'latest')}-management",
                                "ports": [
                                    {"containerPort": 5672},
                                    {"containerPort": 15672}
                                ],
                                "env": [
                                    {"name": "RABBITMQ_DEFAULT_USER", "value": "guest"},
                                    {"name": "RABBITMQ_DEFAULT_PASS", "value": "guest"}
                                ],
                                "volumeMounts": [{
                                    "name": "rabbitmq-data",
                                    "mountPath": "/var/lib/rabbitmq"
                                }]
                            }],
                            "volumes": [{
                                "name": "rabbitmq-data",
                                "persistentVolumeClaim": {
                                    "claimName": "rabbitmq-data-claim"
                                }
                            }]
                        }
                    }
                }
            }
            resources.append(mq_deployment)
            
            # Create RabbitMQ service
            mq_service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "queue",
                    "namespace": namespace,
                    "labels": {
                        "app": "queue",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "selector": {
                        "app": "queue"
                    },
                    "ports": [
                        {"port": 5672, "targetPort": 5672, "name": "amqp"},
                        {"port": 15672, "targetPort": 15672, "name": "management"}
                    ]
                }
            }
            resources.append(mq_service)
            
            # Create PVC for RabbitMQ
            mq_pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": "rabbitmq-data-claim",
                    "namespace": namespace,
                    "labels": {
                        "app": "queue",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {
                        "requests": {
                            "storage": infrastructure['message_queue'].get('storage', '1Gi')
                        }
                    }
                }
            }
            resources.append(mq_pvc)
    
    # Handle cache (Redis)
    if 'cache' in infrastructure and infrastructure['cache'].get('enabled', False) and infrastructure['cache'].get('in_cluster', False):
        cache_engine = infrastructure['cache'].get('engine', 'redis')
        
        if cache_engine == 'redis':
            # Create Redis deployment
            redis_deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "redis",
                    "namespace": namespace,
                    "labels": {
                        "app": "redis",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {
                        "matchLabels": {
                            "app": "redis"
                        }
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "app": "redis"
                            }
                        },
                        "spec": {
                            "containers": [{
                                "name": "redis",
                                "image": f"redis:{infrastructure['cache'].get('version', 'latest')}",
                                "ports": [{"containerPort": 6379}],
                                "args": ["--requirepass", "password"] if infrastructure['cache'].get('auth_enabled', False) else [],
                                "volumeMounts": [{
                                    "name": "redis-data",
                                    "mountPath": "/data"
                                }]
                            }],
                            "volumes": [{
                                "name": "redis-data",
                                "persistentVolumeClaim": {
                                    "claimName": "redis-data-claim"
                                }
                            }]
                        }
                    }
                }
            }
            resources.append(redis_deployment)
            
            # Create Redis service
            redis_service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "redis",
                    "namespace": namespace,
                    "labels": {
                        "app": "redis",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "selector": {
                        "app": "redis"
                    },
                    "ports": [{
                        "port": 6379,
                        "targetPort": 6379
                    }]
                }
            }
            resources.append(redis_service)
            
            # Create PVC for Redis
            redis_pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": "redis-data-claim",
                    "namespace": namespace,
                    "labels": {
                        "app": "redis",
                        "managed-by": "buildandburn"
                    }
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {
                        "requests": {
                            "storage": infrastructure['cache'].get('storage', '1Gi')
                        }
                    }
                }
            }
            resources.append(redis_pvc)
    
    return resources

def create_helm_chart(manifest, output_dir):
    """Create a Helm chart from generated Kubernetes manifests.
    
    Args:
        manifest: The manifest configuration
        output_dir: Directory to write manifests
        
    Returns:
        Path to the Helm chart directory
    """
    app_name = manifest['name']
    chart_dir = os.path.join(output_dir, "chart")
    templates_dir = os.path.join(chart_dir, "templates")
    
    # Create the chart directory structure
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create Chart.yaml
    chart_yaml = {
        "apiVersion": "v2",
        "name": app_name,
        "description": f"A Helm chart for {app_name}",
        "type": "application",
        "version": "0.1.0",
        "appVersion": manifest.get('version', '1.0.0')
    }
    
    with open(os.path.join(chart_dir, "Chart.yaml"), 'w') as f:
        yaml.dump(chart_yaml, f)
    
    # Create values.yaml
    values = {
        "global": {
            "namespace": f"bb-{app_name}"
        },
        "services": {}
    }
    
    if 'services' in manifest:
        for service in manifest['services']:
            values['services'][service['name']] = {
                "enabled": True,
                "image": service['image'],
                "replicas": service.get('replicas', 1)
            }
    
    # Add ingress configuration if present
    if 'ingress' in manifest:
        values['ingress'] = {
            "enabled": True
        }
        
        if isinstance(manifest['ingress'], dict):
            values['ingress']['domain'] = manifest['ingress'].get('domain', 'example.com')
        elif isinstance(manifest['ingress'], list) and len(manifest['ingress']) > 0:
            # Extract domain from the first ingress with a host
            for ing in manifest['ingress']:
                if 'host' in ing:
                    domain_parts = ing['host'].split('.')
                    if len(domain_parts) >= 2:
                        values['ingress']['domain'] = '.'.join(domain_parts[1:])
                        break
    
    with open(os.path.join(chart_dir, "values.yaml"), 'w') as f:
        yaml.dump(values, f)
    
    # Create _helpers.tpl
    helpers_content = """{{/* Generate basic labels */}}
{{- define "app.labels" -}}
app.kubernetes.io/name: {{ .Release.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Release.Name }}-{{ .Release.Service }}
{{- end -}}
"""
    
    with open(os.path.join(templates_dir, "_helpers.tpl"), 'w') as f:
        f.write(helpers_content)
    
    # Create namespace.yaml
    namespace_content = """# This file is intentionally commented out to prevent namespace ownership conflicts.
# The namespace will be created by the buildandburn CLI tool before Helm runs.
# If you need to use this template, remove the comments and ensure proper Helm ownership.
#
# apiVersion: v1
# kind: Namespace
# metadata:
#   name: {{ .Values.global.namespace }}
#   labels:
#     {{- include "app.labels" . | nindent 4 }}
#     managed-by: buildandburn
"""
    
    with open(os.path.join(templates_dir, "namespace.yaml"), 'w') as f:
        f.write(namespace_content)
    
    # Create deployment.yaml
    deployment_content = """{{- range $name, $config := .Values.services }}
{{- if $config.enabled }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  namespace: {{ $.Values.global.namespace }}
  labels:
    {{- include "app.labels" $ | nindent 4 }}
    app: {{ $name }}
spec:
  replicas: {{ $config.replicas }}
  selector:
    matchLabels:
      app: {{ $name }}
  template:
    metadata:
      labels:
        app: {{ $name }}
    spec:
      containers:
      - name: {{ $name }}
        image: {{ $config.image }}
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          protocol: TCP
{{- end }}
{{- end }}
"""
    
    with open(os.path.join(templates_dir, "deployment.yaml"), 'w') as f:
        f.write(deployment_content)
    
    # Create service.yaml
    service_content = """{{- range $name, $config := .Values.services }}
{{- if $config.enabled }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $name }}
  namespace: {{ $.Values.global.namespace }}
  labels:
    {{- include "app.labels" $ | nindent 4 }}
    app: {{ $name }}
spec:
  selector:
    app: {{ $name }}
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
{{- end }}
{{- end }}
"""
    
    with open(os.path.join(templates_dir, "service.yaml"), 'w') as f:
        f.write(service_content)
    
    # Create ingress.yaml if needed
    if 'ingress' in values and values['ingress']['enabled']:
        ingress_content = """{{- if .Values.ingress.enabled }}
{{- range $name, $config := .Values.services }}
{{- if $config.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ $name }}
  namespace: {{ $.Values.global.namespace }}
  labels:
    {{- include "app.labels" $ | nindent 4 }}
    app: {{ $name }}
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: "{{ $name }}.{{ $.Values.ingress.domain }}"
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {{ $name }}
            port:
              number: 80
{{- end }}
{{- end }}
{{- end }}
"""
        
        with open(os.path.join(templates_dir, "ingress.yaml"), 'w') as f:
            f.write(ingress_content)
    
    print_success(f"Created Helm chart at {chart_dir}")
    return chart_dir

def main():
    parser = argparse.ArgumentParser(description="Generate Kubernetes manifests from application specifications")
    parser.add_argument("manifest", help="Path to the manifest file (YAML or JSON)")
    parser.add_argument("-o", "--output", help="Output directory for the generated manifests", default="k8s")
    parser.add_argument("--helm", action="store_true", help="Generate a Helm chart instead of raw manifests")
    parser.add_argument("--all", action="store_true", help="Generate both raw manifests and a Helm chart")
    
    args = parser.parse_args()
    
    print_info("=" * 80)
    print_info("KUBERNETES MANIFEST GENERATOR")
    print_info("=" * 80)
    
    # Load manifest
    print_info(f"Loading manifest file: {args.manifest}")
    manifest = load_manifest(args.manifest)
    if not manifest:
        return 1
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists(args.output):
        output_dir = os.path.join(args.output, f"generated_{timestamp}")
    else:
        output_dir = args.output
    
    print_info(f"Generating Kubernetes manifests in: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate manifests
    if args.helm or args.all:
        chart_dir = create_helm_chart(manifest, output_dir)
        print_success(f"Helm chart generated at: {chart_dir}")
    
    if not args.helm or args.all:
        manifests_dir = os.path.join(output_dir, "manifests")
        resources = generate_manifests(manifest, manifests_dir)
        print_success(f"Kubernetes manifests generated at: {manifests_dir}")
    
    print_info("=" * 80)
    print_success("MANIFEST GENERATION COMPLETED")
    print_info("=" * 80)
    
    if args.helm:
        print_info(f"To use the Helm chart: helm install {manifest['name']} {os.path.join(output_dir, 'chart')}")
    else:
        print_info(f"To apply the manifests: kubectl apply -f {os.path.join(output_dir, 'manifests', 'all.yaml')}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 