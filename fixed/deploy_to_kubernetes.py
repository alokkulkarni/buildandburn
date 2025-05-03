def deploy_to_kubernetes(manifest, tf_output, k8s_dir, project_dir):
    """Deploy services to Kubernetes."""
    print_info("=" * 80)
    print_info("DEPLOYING TO KUBERNETES")
    print_info("=" * 80)
    
    # Get kubeconfig
    print_info("Retrieving kubeconfig from Terraform outputs...")
    if 'kubeconfig' not in tf_output or 'value' not in tf_output['kubeconfig']:
        print_warning("Kubeconfig not found in Terraform outputs, attempting to get it from the EKS cluster")
        # Try to get the kubeconfig from the EKS cluster directly
        try:
            # Check if cluster_name is available in terraform output
            if 'cluster_name' in tf_output and 'value' in tf_output['cluster_name']:
                cluster_name = tf_output['cluster_name']['value']
                region = manifest.get('region', 'us-west-2')
                
                print_info(f"Getting kubeconfig for EKS cluster: {cluster_name} in region {region}")
                update_kubeconfig_cmd = ["aws", "eks", "update-kubeconfig", 
                                        "--name", cluster_name, 
                                        "--region", region]
                
                result = run_command(update_kubeconfig_cmd, capture_output=True)
                if result.returncode == 0:
                    print_success("Successfully obtained kubeconfig from EKS cluster")
                    # Get the kubeconfig from the default location
                    home = os.path.expanduser("~")
                    default_kubeconfig = os.path.join(home, ".kube", "config")
                    if os.path.exists(default_kubeconfig):
                        with open(default_kubeconfig, 'r') as kf:
                            kubeconfig = kf.read()
                        kubeconfig_path = os.path.join(project_dir, "kubeconfig")
                        print_info(f"Saving kubeconfig to: {kubeconfig_path}")
                        with open(kubeconfig_path, 'w') as f:
                            f.write(kubeconfig)
                    else:
                        print_error("Default kubeconfig not found after update")
                        return False
                else:
                    print_error(f"Failed to get kubeconfig for EKS cluster: {result.stderr}")
                    return False
            else:
                print_error("Cluster name not found in Terraform outputs")
                return False
        except Exception as e:
            print_error(f"Error getting kubeconfig from EKS cluster: {str(e)}")
            return False
    else:
        kubeconfig = tf_output['kubeconfig']['value']
        kubeconfig_path = os.path.join(project_dir, "kubeconfig")
        print_info(f"Saving kubeconfig to: {kubeconfig_path}")
        with open(kubeconfig_path, 'w') as f:
            f.write(kubeconfig)
    
    # Rest of the function omitted for brevity
    return True 