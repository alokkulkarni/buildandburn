output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "kubeconfig" {
  description = "Kubeconfig for the EKS cluster"
  value       = module.eks.kubeconfig
  sensitive   = true
}

output "database_endpoint" {
  description = "Endpoint for the database"
  value       = length(module.rds) > 0 ? module.rds[0].db_endpoint : null
}

output "database_username" {
  description = "Username for the database"
  value       = length(module.rds) > 0 ? module.rds[0].db_username : null
  sensitive   = true
}

output "database_password" {
  description = "Password for the database"
  value       = length(module.rds) > 0 ? module.rds[0].db_password : null
  sensitive   = true
}

output "mq_endpoint" {
  description = "Endpoint for the message queue"
  value       = length(module.mq) > 0 ? module.mq[0].mq_endpoint : null
}

output "mq_username" {
  description = "Username for the message queue"
  value       = length(module.mq) > 0 ? module.mq[0].mq_username : null
  sensitive   = true
}

output "mq_password" {
  description = "Password for the message queue"
  value       = length(module.mq) > 0 ? module.mq[0].mq_password : null
  sensitive   = true
}

# ElastiCache outputs
output "redis_primary_endpoint" {
  description = "The primary endpoint of the ElastiCache cluster"
  value       = contains(var.dependencies, "redis") ? module.elasticache[0].primary_endpoint_address : null
}

output "redis_reader_endpoint" {
  description = "The reader endpoint of the ElastiCache cluster"
  value       = contains(var.dependencies, "redis") ? module.elasticache[0].reader_endpoint_address : null
}

output "redis_port" {
  description = "The port on which the ElastiCache cluster accepts connections"
  value       = contains(var.dependencies, "redis") ? module.elasticache[0].port : null
}

output "redis_connection_url" {
  description = "The connection URL for the ElastiCache cluster (sensitive)"
  value       = contains(var.dependencies, "redis") ? module.elasticache[0].connection_url : null
  sensitive   = true
}

output "redis_secrets_arn" {
  description = "The ARN of the Secrets Manager secret containing ElastiCache credentials"
  value       = contains(var.dependencies, "redis") && var.redis_auth_enabled ? module.elasticache[0].secrets_manager_secret_arn : null
} 