output "primary_endpoint_address" {
  description = "The primary endpoint address of the ElastiCache cluster"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "The reader endpoint address of the ElastiCache cluster"
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "port" {
  description = "The port on which the ElastiCache cluster accepts connections"
  value       = local.redis_port
}

output "security_group_id" {
  description = "The ID of the security group used by the ElastiCache cluster"
  value       = aws_security_group.elasticache.id
}

output "connection_info" {
  description = "Connection information for the ElastiCache cluster"
  value = {
    host           = aws_elasticache_replication_group.main.primary_endpoint_address
    port           = local.redis_port
    auth_enabled   = var.auth_enabled
    tls_enabled    = var.transit_encryption_enabled
  }
  sensitive = true
}

output "connection_url" {
  description = "Connection URL for the ElastiCache cluster"
  value = "${var.transit_encryption_enabled ? "rediss" : "redis"}://${var.auth_enabled ? ":${random_password.redis_auth[0].result}@" : ""}${aws_elasticache_replication_group.main.primary_endpoint_address}:${local.redis_port}"
  sensitive = true
}

output "replication_group_id" {
  description = "The ID of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.id
}

output "arn" {
  description = "The ARN of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.arn
}

output "auth_token" {
  description = "The auth token for the ElastiCache cluster (if AUTH is enabled)"
  value       = var.auth_enabled ? random_password.redis_auth[0].result : null
  sensitive   = true
}

output "secrets_manager_secret_arn" {
  description = "The ARN of the Secrets Manager secret containing ElastiCache credentials (if AUTH is enabled)"
  value       = var.auth_enabled ? aws_secretsmanager_secret.redis_credentials[0].arn : null
} 