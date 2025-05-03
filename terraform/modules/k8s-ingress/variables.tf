variable "chart_version" {
  description = "Version of the ingress-nginx Helm chart to install"
  type        = string
  default     = "4.7.1" # Use the latest stable version at the time of implementation
}

variable "eks_node_group_id" {
  description = "ID of the EKS node group to depend on"
  type        = string
}

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env_id" {
  description = "Unique identifier for this environment"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
} 