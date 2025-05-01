locals {
  cache_name = "${var.project_name}-${var.env_id}"
  redis_port = 6379
}

# Generate a random password for Redis AUTH if enabled
resource "random_password" "redis_auth" {
  count   = var.auth_enabled ? 1 : 0
  length  = 16
  special = false
}

# Security group for ElastiCache
resource "aws_security_group" "elasticache" {
  name        = "${local.cache_name}-elasticache-sg"
  description = "Security group for ElastiCache Redis cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = local.redis_port
    to_port         = local.redis_port
    protocol        = "tcp"
    description     = "Allow Redis traffic from EKS"
    security_groups = [var.eks_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.cache_name}-elasticache-sg"
    }
  )
}

# Subnet group for ElastiCache
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.cache_name}-elasticache-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${local.cache_name}-elasticache-subnet-group"
    }
  )
}

# Parameter group for ElastiCache
resource "aws_elasticache_parameter_group" "main" {
  name   = "${local.cache_name}-elasticache-params"
  family = "redis${var.engine_version}"

  # Enable encryption in transit if TLS is enabled
  dynamic "parameter" {
    for_each = var.transit_encryption_enabled ? [1] : []
    content {
      name  = "transit-encryption-enabled"
      value = "yes"
    }
  }

  # Enable Redis AUTH if authentication is enabled
  dynamic "parameter" {
    for_each = var.auth_enabled ? [1] : []
    content {
      name  = "auth-enabled"
      value = "yes"
    }
  }

  # Set specific Redis parameters based on configuration
  parameter {
    name  = "maxmemory-policy"
    value = var.maxmemory_policy
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.cache_name}-elasticache-params"
    }
  )
}

# ElastiCache Redis cluster
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${local.cache_name}-redis"
  description                = "Redis cluster for ${var.project_name}"
  node_type                  = var.node_type
  num_cache_clusters         = var.cluster_size
  engine_version             = var.engine_version
  port                       = local.redis_port
  parameter_group_name       = aws_elasticache_parameter_group.main.name
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.elasticache.id]
  automatic_failover_enabled = var.cluster_size > 1 ? true : false
  multi_az_enabled           = var.cluster_size > 1 ? var.multi_az_enabled : false
  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  transit_encryption_enabled = var.transit_encryption_enabled
  auth_token                 = var.auth_enabled ? random_password.redis_auth[0].result : null
  
  # Maintenance and backup settings
  maintenance_window         = var.maintenance_window
  snapshot_window            = var.snapshot_window
  snapshot_retention_limit   = var.snapshot_retention_limit
  apply_immediately          = true
  auto_minor_version_upgrade = true

  tags = merge(
    var.tags,
    {
      Name = "${local.cache_name}-redis"
    }
  )
}

# Store Redis credentials in AWS Secrets Manager
resource "aws_secretsmanager_secret" "redis_credentials" {
  count       = var.auth_enabled ? 1 : 0
  name        = "${var.project_name}-${var.env_id}-cache-credentials"
  description = "Redis credentials for build-and-burn environment"
  
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  count     = var.auth_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.redis_credentials[0].id
  
  secret_string = jsonencode({
    host         = aws_elasticache_replication_group.main.primary_endpoint_address
    port         = local.redis_port
    auth_enabled = var.auth_enabled
    auth_token   = var.auth_enabled ? random_password.redis_auth[0].result : null
    tls_enabled  = var.transit_encryption_enabled
    connection_url = "${var.transit_encryption_enabled ? "rediss" : "redis"}://${var.auth_enabled ? ":${random_password.redis_auth[0].result}@" : ""}${aws_elasticache_replication_group.main.primary_endpoint_address}:${local.redis_port}"
  })
} 