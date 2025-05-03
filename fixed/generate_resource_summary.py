def generate_resource_summary(manifest, tf_vars, terraform_project_dir):
    """
    Generate a summary of resources that will be created and their estimated costs.
    
    This function analyzes the Terraform configuration and manifest to provide
    a summary of AWS resources that will be provisioned and their approximate costs.
    
    Args:
        manifest (dict): The parsed manifest containing configuration
        tf_vars (dict): Terraform variables prepared from the manifest
        terraform_project_dir (str): Path to Terraform project directory
        
    Returns:
        tuple: (list of resources, float of total hourly cost)
    """
    # Initialize resource list and cost
    resources = []
    total_cost_per_hour = 0.0
    
    # Helper function to add a resource to the summary
    def add_resource(type_name, name, count, cost_per_hour):
        nonlocal total_cost_per_hour
        resources.append({
            "type": type_name,
            "name": name,
            "count": count,
            "cost_per_hour": cost_per_hour
        })
        total_cost_per_hour += cost_per_hour * count
    
    # EKS Cluster - always included
    add_resource(
        "EKS Cluster", 
        f"{tf_vars['project_name']}-{tf_vars['env_id']}", 
        1, 
        0.10  # Approximate cost per hour for EKS control plane
    )
    
    # EKS Nodes based on configuration
    instance_type = tf_vars['eks_instance_types'][0]
    node_count = tf_vars['eks_node_min']
    
    # Approximate cost mapping for common instance types
    instance_costs = {
        "t3.small": 0.02,
        "t3.medium": 0.04,
        "t3.large": 0.08,
        "m5.large": 0.10,
        "m5.xlarge": 0.20,
        "c5.large": 0.09,
        "c5.xlarge": 0.18,
        "r5.large": 0.13,
        "r5.xlarge": 0.26
    }
    
    instance_cost = instance_costs.get(instance_type, 0.04)  # Default to t3.medium cost
    add_resource(
        "EC2 Instance",
        f"eks-node-{instance_type}",
        node_count,
        instance_cost
    )
    
    # Add database if included
    if 'database' in tf_vars.get('dependencies', []):
        db_instance_class = tf_vars.get('db_instance_class', 'db.t3.micro')
        db_storage = tf_vars.get('db_allocated_storage', 20)
        
        # Approximate cost mapping for common RDS instance classes
        db_costs = {
            "db.t3.micro": 0.02,
            "db.t3.small": 0.04,
            "db.t3.medium": 0.08,
            "db.m5.large": 0.15,
            "db.m5.xlarge": 0.30
        }
        
        db_cost = db_costs.get(db_instance_class, 0.02)  # Default to micro cost
        storage_cost = 0.115 * db_storage / 30 / 24  # Approximate cost per GB per hour
        
        add_resource(
            "RDS Database",
            f"{tf_vars['project_name']}-{tf_vars['env_id']}-db",
            1,
            db_cost + storage_cost
        )
    
    # Rest of the function (omitted for brevity)
    
    return resources, total_cost_per_hour 