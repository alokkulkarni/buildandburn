# Build and Burn Terraform Modules

This directory contains Terraform modules for the Build and Burn system. These modules are designed to be used together to create a complete environment based on a manifest file.

## Core Infrastructure Modules

- **vpc**: Creates a VPC with public and private subnets
- **eks**: Creates an Amazon EKS cluster with managed node groups
- **rds**: Creates an Amazon RDS database instance
- **mq**: Creates an Amazon MQ broker
- **elasticache**: Creates an Amazon ElastiCache Redis cluster

## Policy Modules

These modules create IAM policies required for connecting services together:

- **eks-to-rds-policy**: Creates a policy that allows EKS nodes to access RDS instances
- **eks-to-mq-policy**: Creates a policy that allows EKS nodes to access MQ brokers
- **eks-to-elasticache-policy**: Creates a policy that allows EKS nodes to access ElastiCache clusters

## Access Policy Modules

These modules provide different levels of access to AWS services:

### RDS Access

- **rds-full-access-policy**: Provides full access to RDS resources
- **rds-write-access-policy**: Provides limited write access to RDS resources (read + specific writes)

### ElastiCache Access

- **elasticache-full-access-policy**: Provides full access to ElastiCache resources
- **elasticache-write-access-policy**: Provides limited write access to ElastiCache resources

### MQ Access

- **mq-full-access-policy**: Provides full access to Amazon MQ resources
- **mq-write-access-policy**: Provides limited write access to Amazon MQ resources

## Usage

The Build and Burn CLI will automatically detect which modules are needed based on the manifest file and will create the necessary infrastructure.

To use these modules directly in your Terraform configuration, see the example configuration in `terraform/example-main.tf`.

Each module can be enabled conditionally based on the dependencies specified in the manifest file:

```terraform
# Example of conditional module usage
module "rds_full_access_policy" {
  source = "./modules/rds-full-access-policy"
  count  = contains(var.dependencies, "database") ? 1 : 0
  
  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags
  
  depends_on = [module.eks]
}
``` 