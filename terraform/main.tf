provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.10"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.5"
    }
  }

  # Use local state instead of S3
  backend "local" {}
}

# Get AWS account ID
data "aws_caller_identity" "current" {}

locals {
  project_name = var.project_name
  env_id       = var.env_id
  account_id   = data.aws_caller_identity.current.account_id
  tags = {
    Environment = "buildandburn-${var.env_id}"
    ManagedBy   = "terraform"
    Project     = var.project_name
  }
}

module "vpc" {
  source = "./modules/vpc"

  project_name = local.project_name
  env_id       = local.env_id
  cidr_block   = var.vpc_cidr
  region       = var.region
  tags         = local.tags
}

module "eks" {
  source = "./modules/eks"

  project_name   = local.project_name
  env_id         = local.env_id
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  instance_types = var.eks_instance_types
  node_min       = var.eks_node_min
  node_max       = var.eks_node_max
  k8s_version    = var.k8s_version
  tags           = local.tags

  depends_on = [module.vpc]
}

# Conditionally create RDS if database is requested
module "rds" {
  source = "./modules/rds"
  count  = contains(var.dependencies, "database") ? 1 : 0

  project_name          = local.project_name
  env_id                = local.env_id
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.database_subnet_ids
  eks_security_group_id = module.eks.cluster_security_group_id
  engine                = var.db_engine
  engine_version        = var.db_engine_version
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  tags                  = local.tags

  depends_on = [module.vpc]
}

# Conditionally create MQ if message queue is requested
module "mq" {
  source = "./modules/mq"
  count  = contains(var.dependencies, "queue") ? 1 : 0

  project_name               = local.project_name
  env_id                     = local.env_id
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnet_ids
  eks_security_group_id      = module.eks.cluster_security_group_id
  engine_type                = var.mq_engine_type
  engine_version             = var.mq_engine_version
  instance_type              = var.mq_instance_type
  auto_minor_version_upgrade = var.mq_auto_minor_version_upgrade
  tags                       = local.tags

  depends_on = [module.vpc]
}

# Conditionally create ElastiCache if redis is requested
module "elasticache" {
  source = "./modules/elasticache"
  count  = contains(var.dependencies, "redis") ? 1 : 0

  project_name          = local.project_name
  env_id                = local.env_id
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  eks_security_group_id = module.eks.cluster_security_group_id

  # Redis configuration
  node_type      = var.redis_node_type
  engine_version = var.redis_engine_version
  cluster_size   = var.redis_cluster_size
  auth_enabled   = var.redis_auth_enabled

  # Advanced configuration
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  multi_az_enabled           = var.redis_multi_az_enabled

  tags = local.tags

  depends_on = [module.vpc]
}

# Conditionally create Kafka if kafka is requested
module "kafka" {
  source = "./modules/kafka"
  count  = contains(var.dependencies, "kafka") ? 1 : 0

  project_name          = local.project_name
  env_id                = local.env_id
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  eks_security_group_id = module.eks.cluster_security_group_id

  # Kafka configuration
  kafka_version    = var.kafka_version
  instance_type    = var.kafka_instance_type
  broker_count     = var.kafka_broker_count
  volume_size      = var.kafka_volume_size
  monitoring_level = var.kafka_monitoring_level

  tags = local.tags

  depends_on = [module.vpc]
}

# Conditionally create EKS to RDS policy if database is requested
module "eks_to_rds_policy" {
  source = "./modules/eks-to-rds-policy"
  count  = contains(var.dependencies, "database") ? 1 : 0

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.rds]
}

# Conditionally create EKS to MQ policy if queue is requested
module "eks_to_mq_policy" {
  source = "./modules/eks-to-mq-policy"
  count  = contains(var.dependencies, "queue") ? 1 : 0

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.mq]
}

# Conditionally create EKS to ElastiCache policy if redis is requested
module "eks_to_elasticache_policy" {
  source = "./modules/eks-to-elasticache-policy"
  count  = contains(var.dependencies, "redis") ? 1 : 0

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.elasticache]
}

# Conditionally create EKS to Kafka policy if kafka is requested
module "eks_to_kafka_policy" {
  source = "./modules/eks-to-kafka-policy"
  count  = contains(var.dependencies, "kafka") ? 1 : 0

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.kafka]
}

# Conditionally create Kafka full access policy if kafka is requested
module "kafka_full_access_policy" {
  source = "./modules/kafka-full-access-policy"
  count  = contains(var.dependencies, "kafka") ? 1 : 0

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.kafka]
}

# Conditionally create Kafka write access policy
module "kafka_write_access_policy" {
  source = "./modules/kafka-write-access-policy"
  count  = contains(var.dependencies, "kafka") ? 0 : 0 # Default disabled, enable as needed

  project_name   = local.project_name
  env_id         = local.env_id
  region         = var.region
  account_id     = local.account_id
  node_role_name = module.eks.node_role_name
  tags           = local.tags

  depends_on = [module.eks, module.kafka]
}

# Configure kubernetes provider with EKS details
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
      command     = "aws"
    }
  }
} 