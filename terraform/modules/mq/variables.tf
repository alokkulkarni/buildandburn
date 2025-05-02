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
  description = "List of subnet IDs for the message broker"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID for the EKS cluster"
  type        = string
}

variable "engine_type" {
  description = "Message broker engine type (e.g., RabbitMQ)"
  type        = string
  default     = "RabbitMQ"
}

variable "engine_version" {
  description = "Message broker engine version"
  type        = string
  default     = "3.13"
}

variable "instance_type" {
  description = "Message broker instance type"
  type        = string
  default     = "mq.t3.micro"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "auto_minor_version_upgrade" {
  description = "Whether to automatically upgrade to new minor versions during the maintenance window"
  type        = bool
  default     = true
} 