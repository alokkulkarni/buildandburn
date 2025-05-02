locals {
  cluster_name = "${var.project_name}-${var.env_id}-kafka"
}

# Security group for Kafka
resource "aws_security_group" "kafka" {
  name        = "${var.project_name}-${var.env_id}-kafka-sg"
  description = "Security group for Amazon MSK (Kafka) cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    description     = "Allow Kafka plaintext traffic"
    security_groups = [var.eks_security_group_id]
  }

  ingress {
    from_port       = 9094
    to_port         = 9094
    protocol        = "tcp"
    description     = "Allow Kafka TLS traffic"
    security_groups = [var.eks_security_group_id]
  }

  ingress {
    from_port       = 9096
    to_port         = 9096
    protocol        = "tcp"
    description     = "Allow Kafka SASL/SCRAM traffic"
    security_groups = [var.eks_security_group_id]
  }

  ingress {
    from_port       = 2181
    to_port         = 2181
    protocol        = "tcp"
    description     = "Allow Zookeeper traffic"
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
      Name = "${var.project_name}-${var.env_id}-kafka-sg"
    }
  )
}

# MSK Configuration
resource "aws_msk_configuration" "main" {
  name              = "${var.project_name}-${var.env_id}-kafka-config"
  kafka_versions    = [var.kafka_version]
  server_properties = <<PROPERTIES
auto.create.topics.enable=true
delete.topic.enable=true
default.replication.factor=2
min.insync.replicas=1
num.partitions=3
log.retention.hours=24
zookeeper.connection.timeout.ms=18000
PROPERTIES

  lifecycle {
    create_before_destroy = true
  }
}

# MSK Cluster
resource "aws_msk_cluster" "main" {
  cluster_name           = local.cluster_name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.instance_type
    client_subnets  = var.subnet_ids
    security_groups = [aws_security_group.kafka.id]
    storage_info {
      ebs_storage_info {
        volume_size = var.volume_size
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
    }
    encryption_at_rest_kms_key_arn = null # Use AWS owned KMS key
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.kafka_logs.name
      }
    }
  }

  tags = merge(
    var.tags,
    {
      Name = local.cluster_name
    }
  )

  depends_on = [aws_cloudwatch_log_group.kafka_logs]
}

# CloudWatch Log Group for Kafka logs
resource "aws_cloudwatch_log_group" "kafka_logs" {
  name              = "/aws/msk/${local.cluster_name}"
  retention_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${local.cluster_name}-logs"
    }
  )
}

# Store Kafka configuration in AWS Secrets Manager
resource "aws_secretsmanager_secret" "kafka_config" {
  name        = "${var.project_name}-${var.env_id}-kafka-config"
  description = "Kafka configuration and credentials for build-and-burn environment"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "kafka_config" {
  secret_id = aws_secretsmanager_secret.kafka_config.id
  secret_string = jsonencode({
    bootstrap_brokers     = aws_msk_cluster.main.bootstrap_brokers,
    bootstrap_brokers_tls = aws_msk_cluster.main.bootstrap_brokers_tls,
    zookeeper_connect     = aws_msk_cluster.main.zookeeper_connect_string,
    kafka_version         = var.kafka_version,
    brokers_count         = var.broker_count
  })
} 