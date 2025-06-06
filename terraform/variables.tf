variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Unique identifier for this environment"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "eks_instance_types" {
  description = "Instance types to use for EKS nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "eks_node_min" {
  description = "Minimum number of nodes in EKS cluster"
  type        = number
  default     = 1
}

variable "eks_node_max" {
  description = "Maximum number of nodes in EKS cluster"
  type        = number
  default     = 3
}

variable "k8s_version" {
  description = "Kubernetes version to use"
  type        = string
  default     = "1.32"
}

variable "dependencies" {
  description = "List of dependencies to deploy (e.g., database, queue)"
  type        = list(string)
  default     = []
}

variable "db_engine" {
  description = "Database engine to use"
  type        = string
  default     = "postgres"
}

variable "db_engine_version" {
  description = "Database engine version"
  type        = string
  default     = "13"
}

variable "db_instance_class" {
  description = "Database instance class"
  type        = string
  default     = "db.t3.small"
}

variable "db_allocated_storage" {
  description = "Allocated storage for database (GB)"
  type        = number
  default     = 20
}

variable "mq_engine_type" {
  description = "Message broker engine type"
  type        = string
  default     = "RabbitMQ"
}

variable "mq_engine_version" {
  description = "Message broker engine version"
  type        = string
  default     = "3.13"
}

variable "mq_instance_type" {
  description = "Message broker instance type"
  type        = string
  default     = "mq.t3.micro"
}

variable "mq_auto_minor_version_upgrade" {
  description = "Whether to automatically upgrade to new minor versions of the message broker during the maintenance window"
  type        = bool
  default     = true
}

# Kafka Configuration Variables
variable "kafka_version" {
  description = "Kafka version"
  type        = string
  default     = "2.8.1"
}

variable "kafka_instance_type" {
  description = "Kafka broker instance type"
  type        = string
  default     = "kafka.t3.small"
}

variable "kafka_broker_count" {
  description = "Number of Kafka broker nodes"
  type        = number
  default     = 2
}

variable "kafka_volume_size" {
  description = "Size of the EBS volume for Kafka broker (GB)"
  type        = number
  default     = 20
}

variable "kafka_monitoring_level" {
  description = "Monitoring level for Kafka cluster (DEFAULT, PER_BROKER, PER_TOPIC_PER_BROKER, or PER_TOPIC_PER_PARTITION)"
  type        = string
  default     = "DEFAULT"
}

# Redis Configuration Variables
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.small"
}

variable "redis_engine_version" {
  description = "ElastiCache Redis engine version"
  type        = string
  default     = "6.2"
}

variable "redis_cluster_size" {
  description = "Number of nodes in the ElastiCache cluster"
  type        = number
  default     = 1
}

variable "redis_auth_enabled" {
  description = "Enable Redis AUTH (password protection)"
  type        = bool
  default     = true
}

variable "redis_multi_az_enabled" {
  description = "Enable Multi-AZ deployment for the ElastiCache cluster"
  type        = bool
  default     = false
}

variable "enable_ingress" {
  description = "Whether to enable and install NGINX ingress controller"
  type        = bool
  default     = true # Enable by default for better user experience
} 