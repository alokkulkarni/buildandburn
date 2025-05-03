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

# Kafka outputs
output "kafka_bootstrap_brokers" {
  description = "Connection host:port pairs for the Kafka cluster (plaintext)"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_bootstrap_brokers : null
}

output "kafka_bootstrap_brokers_tls" {
  description = "TLS Connection host:port pairs for the Kafka cluster"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_bootstrap_brokers_tls : null
}

output "kafka_bootstrap_brokers_sasl_scram" {
  description = "SASL SCRAM Connection host:port pairs for the Kafka cluster"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_bootstrap_brokers_sasl_scram : null
}

output "kafka_zookeeper_connect_string" {
  description = "Zookeeper connection string for the Kafka cluster"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_zookeeper_connect_string : null
}

output "kafka_arn" {
  description = "ARN of the Kafka cluster"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_arn : null
}

output "kafka_secret_arn" {
  description = "ARN of the secret containing Kafka configuration"
  value       = contains(var.dependencies, "kafka") ? module.kafka[0].kafka_secret_arn : null
}

# Ingress controller outputs
output "ingress_controller_enabled" {
  description = "Whether the ingress controller is enabled"
  value       = var.enable_ingress
}

output "ingress_controller_hostname" {
  description = "The hostname of the ingress controller load balancer"
  value       = var.enable_ingress ? module.k8s_ingress[0].ingress_hostname : null
}

output "ingress_controller_ip" {
  description = "The IP address of the ingress controller load balancer"
  value       = var.enable_ingress ? module.k8s_ingress[0].ingress_ip : null
}

output "ingress_controller_namespace" {
  description = "The namespace where the ingress controller is deployed"
  value       = var.enable_ingress ? module.k8s_ingress[0].ingress_namespace : null
} 