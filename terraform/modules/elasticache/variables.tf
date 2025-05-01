variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Environment ID"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where ElastiCache will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs where ElastiCache will be deployed"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID of the EKS cluster"
  type        = string
}

variable "node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.small"
}

variable "engine_version" {
  description = "ElastiCache Redis engine version"
  type        = string
  default     = "6.2"
}

variable "cluster_size" {
  description = "Number of nodes in the ElastiCache cluster"
  type        = number
  default     = 1
}

variable "auth_enabled" {
  description = "Enable Redis AUTH (password protection)"
  type        = bool
  default     = true
}

variable "multi_az_enabled" {
  description = "Enable Multi-AZ deployment for the ElastiCache cluster"
  type        = bool
  default     = false
}

variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest for the ElastiCache cluster"
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Enable encryption in transit (TLS) for the ElastiCache cluster"
  type        = bool
  default     = true
}

variable "maxmemory_policy" {
  description = "Redis maxmemory policy"
  type        = string
  default     = "volatile-lru"
}

variable "maintenance_window" {
  description = "Maintenance window for the ElastiCache cluster"
  type        = string
  default     = "sun:05:00-sun:06:00"
}

variable "snapshot_window" {
  description = "Snapshot window for the ElastiCache cluster"
  type        = string
  default     = "03:00-04:00"
}

variable "snapshot_retention_limit" {
  description = "Number of days to retain ElastiCache snapshots"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}