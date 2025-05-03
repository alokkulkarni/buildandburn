def get_access_info(kubeconfig_path, namespace, tf_output):
    """
    Get access information for the deployed services.
    
    This function uses kubectl to get information about deployed services and ingresses
    in the Kubernetes cluster.
    
    Args:
        kubeconfig_path (str): Path to the kubeconfig file
        namespace (str): Kubernetes namespace to get resources from
        tf_output (dict): Terraform outputs
        
    Returns:
        dict: Dictionary with access information
    """
    # Initialize access info structure
    access_info = {
        "services": {},
        "ingresses": {},
        "resources": {}
    }
    
    # Check if the kubeconfig file exists
    if not os.path.exists(kubeconfig_path):
        print_warning(f"Kubeconfig not found at {kubeconfig_path}. Cannot retrieve access information.")
        return access_info
    
    # Set up environment for kubectl
    env = os.environ.copy()
    env["KUBECONFIG"] = kubeconfig_path
        
    # Create a log file for recording command outputs
    log_file = open(f"{os.path.dirname(kubeconfig_path)}/access_info.log", "w")
    log_file.write(f"Gathering access information for namespace: {namespace}\n")
    
    try:
        # Get services
        service_cmd = ["kubectl", "get", "service", "-n", namespace, "-o", "wide"]
        print_info(f"Running: {' '.join(service_cmd)}")
        log_file.write(f"Service command: {' '.join(service_cmd)}\n")
        
        service_process = subprocess.run(
            service_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if service_process.returncode == 0 and service_process.stdout.strip():
            log_file.write(f"Service output: {service_process.stdout}\n")
            print_info(f"Deployed services:\n{service_process.stdout}")
        else:
            print_info("No services deployed or found.")
            log_file.write("No services deployed or found.\n")
        
        # Get ingresses
        ingress_cmd = ["kubectl", "get", "ingress", "-n", namespace, "-o", "wide"]
        print_info(f"Running: {' '.join(ingress_cmd)}")
        log_file.write(f"Ingress command: {' '.join(ingress_cmd)}\n")
        
        ingress_process = subprocess.run(
            ingress_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if ingress_process.returncode == 0 and ingress_process.stdout.strip():
            log_file.write(f"Ingress output: {ingress_process.stdout}\n")
            print_info(f"Deployed ingresses:\n{ingress_process.stdout}")
        else:
            print_info("No ingresses deployed or found.")
            log_file.write("No ingresses deployed or found.\n")
        
        # Get service endpoints using JSON format
        service_result = run_command(
            ["kubectl", "get", "service", "-n", namespace, "-o", "json"],
            env=env,
            capture_output=True,
            allow_fail=True
        )
        
        # Get service information
        if hasattr(service_result, 'stdout') and service_result.returncode == 0:
            try:
                services = json.loads(service_result.stdout)
                
                # Service endpoints
                for svc in services.get("items", []):
                    svc_name = svc["metadata"]["name"]
                    svc_type = svc["spec"]["type"]
                    
                    # Handle different service types
                    if svc_type == "LoadBalancer":
                        if "status" in svc and "loadBalancer" in svc["status"] and "ingress" in svc["status"]["loadBalancer"]:
                            lb = svc["status"]["loadBalancer"]["ingress"][0]
                            if "hostname" in lb:
                                access_info["services"][svc_name] = f"http://{lb['hostname']}"
                            elif "ip" in lb:
                                access_info["services"][svc_name] = f"http://{lb['ip']}"
                        else:
                            access_info["services"][svc_name] = f"LoadBalancer pending for {svc_name}"
                    elif svc_type == "NodePort":
                        if "nodePort" in svc["spec"]["ports"][0]:
                            node_port = svc["spec"]["ports"][0]["nodePort"]
                            access_info["services"][svc_name] = f"NodePort {node_port} (requires node IP)"
                    elif svc_type == "ClusterIP":
                        cluster_ip = svc["spec"]["clusterIP"]
                        access_info["services"][svc_name] = f"ClusterIP {cluster_ip} (internal only)"
            except json.JSONDecodeError:
                print_warning("Failed to parse service information as JSON")
                log_file.write("Failed to parse service information as JSON\n")
        
        # Get ingress endpoints using list format
        ingress_result = run_command(
            ["kubectl", "get", "ingress", "-n", namespace, "-o", "json"], 
            env=env,
            capture_output=True, 
            allow_fail=True
        )
        
        # Get ingress information
        if hasattr(ingress_result, 'stdout') and ingress_result.returncode == 0:
            try:
                ingresses = json.loads(ingress_result.stdout)
                
                # Ingress endpoints
                for ing in ingresses.get("items", []):
                    ing_name = ing["metadata"]["name"]
                    
                    # Try to get the host and status
                    if "status" in ing and "loadBalancer" in ing["status"] and "ingress" in ing["status"]["loadBalancer"]:
                        # Find hosts in the ingress spec
                        hosts = []
                        if "spec" in ing and "rules" in ing["spec"]:
                            for rule in ing["spec"]["rules"]:
                                if "host" in rule:
                                    hosts.append(rule["host"])
                        
                        # Get the load balancer addresses (could be hostnames or IPs)
                        lb_addresses = []
                        for lb in ing["status"]["loadBalancer"]["ingress"]:
                            if "hostname" in lb:
                                lb_addresses.append(lb["hostname"])
                            elif "ip" in lb:
                                lb_addresses.append(lb["ip"])
                        
                        # Determine the URL to show
                        if hosts and lb_addresses:
                            # If we have both hosts and lb addresses, use host for a nicer URL
                            host = hosts[0]
                            access_info["ingresses"][ing_name] = f"http://{host}"
                        elif lb_addresses:
                            # Otherwise just use the LB address directly
                            access_info["ingresses"][ing_name] = f"http://{lb_addresses[0]}"
                        else:
                            access_info["ingresses"][ing_name] = f"Ingress address pending for {ing_name}"
                    else:
                        access_info["ingresses"][ing_name] = f"Ingress address pending for {ing_name}"
            except json.JSONDecodeError:
                print_warning("Failed to parse ingress information as JSON")
                log_file.write("Failed to parse ingress information as JSON\n")

        # Check terraform outputs for ingress controller information
        # This is used when the user doesn't deploy specific ingresses but can use the ingress controller directly
        if not access_info["ingresses"] and tf_output and "ingress_controller_hostname" in tf_output and tf_output["ingress_controller_hostname"]["value"]:
            ingress_hostname = tf_output["ingress_controller_hostname"]["value"]
            if ingress_hostname:
                access_info["ingresses"]["nginx-ingress-controller"] = f"http://{ingress_hostname}"
                print_info(f"Found NGINX Ingress Controller at: http://{ingress_hostname}")
                log_file.write(f"Found NGINX Ingress Controller at: http://{ingress_hostname}\n")
        elif not access_info["ingresses"] and tf_output and "ingress_controller_ip" in tf_output and tf_output["ingress_controller_ip"]["value"]:
            ingress_ip = tf_output["ingress_controller_ip"]["value"]
            if ingress_ip:
                access_info["ingresses"]["nginx-ingress-controller"] = f"http://{ingress_ip}"
                print_info(f"Found NGINX Ingress Controller at: http://{ingress_ip}")
                log_file.write(f"Found NGINX Ingress Controller at: http://{ingress_ip}\n")
    
        # Add a 'primary_url' field that identifies the main application URL
        # Determine the primary URL from ingresses or services
        if access_info["ingresses"]:
            # Prefer the first ingress
            primary_ingress = list(access_info["ingresses"].keys())[0]
            access_info["primary_url"] = access_info["ingresses"][primary_ingress]
        elif access_info["services"]:
            # If no ingresses, use the first LoadBalancer service
            for svc_name, svc_url in access_info["services"].items():
                if svc_url.startswith("http://"):
                    access_info["primary_url"] = svc_url
                    break
                    
        # Add other resources too (Databases, Queues, etc.)
        if tf_output:
            # Database
            if "database_endpoint" in tf_output and tf_output["database_endpoint"]["value"]:
                access_info["resources"]["database"] = {
                    "endpoint": tf_output["database_endpoint"]["value"],
                    "username": tf_output["database_username"]["value"] if "database_username" in tf_output else None,
                    # Password is not included here for security reasons
                }
                
            # Message Queue
            if "mq_endpoint" in tf_output and tf_output["mq_endpoint"]["value"]:
                access_info["resources"]["queue"] = {
                    "endpoint": tf_output["mq_endpoint"]["value"],
                    "username": tf_output["mq_username"]["value"] if "mq_username" in tf_output else None,
                    # Password is not included here for security reasons
                }
                
            # Redis
            if "redis_primary_endpoint" in tf_output and tf_output["redis_primary_endpoint"]["value"]:
                access_info["resources"]["redis"] = {
                    "primary_endpoint": tf_output["redis_primary_endpoint"]["value"],
                    "reader_endpoint": tf_output["redis_reader_endpoint"]["value"] if "redis_reader_endpoint" in tf_output else None,
                    "port": tf_output["redis_port"]["value"] if "redis_port" in tf_output else 6379,
                }
                
            # Kafka
            if "kafka_bootstrap_brokers" in tf_output and tf_output["kafka_bootstrap_brokers"]["value"]:
                access_info["resources"]["kafka"] = {
                    "bootstrap_brokers": tf_output["kafka_bootstrap_brokers"]["value"],
                    "bootstrap_brokers_tls": tf_output["kafka_bootstrap_brokers_tls"]["value"] if "kafka_bootstrap_brokers_tls" in tf_output else None,
                }
    except Exception as e:
        print_error(f"Error getting access information: {str(e)}")
        log_file.write(f"Error getting access information: {str(e)}\n")
        traceback.print_exc(file=log_file)
    finally:
        log_file.close()
    
    return access_info 