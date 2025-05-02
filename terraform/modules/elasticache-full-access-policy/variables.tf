variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Environment ID"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "node_role_name" {
  description = "Name of the EKS node IAM role to attach the policy to"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
} 