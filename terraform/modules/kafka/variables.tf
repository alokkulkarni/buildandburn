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
  description = "List of subnet IDs for the Kafka cluster"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID for the EKS cluster"
  type        = string
}

variable "kafka_version" {
  description = "Kafka version"
  type        = string
  default     = "2.8.1"
}

variable "instance_type" {
  description = "Kafka broker instance type"
  type        = string
  default     = "kafka.t3.small"
}

variable "broker_count" {
  description = "Number of Kafka broker nodes"
  type        = number
  default     = 2
}

variable "volume_size" {
  description = "Size of the EBS volume for Kafka broker (GB)"
  type        = number
  default     = 20
}

variable "monitoring_level" {
  description = "Monitoring level for Kafka cluster"
  type        = string
  default     = "DEFAULT"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
} 