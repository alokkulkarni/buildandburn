variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Unique identifier for this environment"
  type        = string
}

variable "region" {
  description = "AWS Region"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "node_role_name" {
  description = "Name of the EKS node IAM role"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
} 