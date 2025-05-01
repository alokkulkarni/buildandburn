variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Unique identifier for this environment"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the EKS cluster"
  type        = list(string)
}

variable "instance_types" {
  description = "List of instance types for the EKS nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min" {
  description = "Minimum number of nodes in the EKS cluster"
  type        = number
  default     = 1
}

variable "node_max" {
  description = "Maximum number of nodes in the EKS cluster"
  type        = number
  default     = 3
}

variable "k8s_version" {
  description = "Kubernetes version to use"
  type        = string
  default     = "1.24"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
} 