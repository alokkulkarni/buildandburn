locals {
  mq_username = "bqadmin"
  mq_password = random_password.mq_password.result
}

# Generate a random password for the message broker
resource "random_password" "mq_password" {
  length  = 16
  special = false
}

# Security group for the message broker
resource "aws_security_group" "mq" {
  name        = "${var.project_name}-${var.env_id}-mq-sg"
  description = "Security group for Amazon MQ broker"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5671
    to_port         = 5671
    protocol        = "tcp"
    description     = "Allow AMQP traffic"
    security_groups = [var.eks_security_group_id]
  }

  ingress {
    from_port       = 5672
    to_port         = 5672
    protocol        = "tcp"
    description     = "Allow AMQP traffic"
    security_groups = [var.eks_security_group_id]
  }

  ingress {
    from_port       = 15672
    to_port         = 15672
    protocol        = "tcp"
    description     = "Allow management console traffic"
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
      Name = "${var.project_name}-${var.env_id}-mq-sg"
    }
  )
}

# Amazon MQ broker
resource "aws_mq_broker" "main" {
  broker_name        = "${var.project_name}-${var.env_id}-mq"
  engine_type        = var.engine_type
  engine_version     = var.engine_version
  host_instance_type = var.instance_type
  
  security_groups    = [aws_security_group.mq.id]
  subnet_ids         = [var.subnet_ids[0]] # Single-instance broker uses only one subnet
  
  user {
    username = local.mq_username
    password = local.mq_password
  }

  # Enable encryption
  encryption_options {
    use_aws_owned_key = true
  }

  # Maintenance preferences
  maintenance_window_start_time {
    day_of_week = "SUNDAY"
    time_of_day = "02:00"
    time_zone   = "UTC"
  }

  logs {
    general = true
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-mq"
    }
  )
}

# Store MQ credentials in AWS Secrets Manager
resource "aws_secretsmanager_secret" "mq_credentials" {
  name        = "${var.project_name}-${var.env_id}-mq-credentials"
  description = "Message broker credentials for build-and-burn environment"
  
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "mq_credentials" {
  secret_id = aws_secretsmanager_secret.mq_credentials.id
  secret_string = jsonencode({
    username      = local.mq_username,
    password      = local.mq_password,
    engine_type   = var.engine_type,
    host          = aws_mq_broker.main.instances[0].endpoints[0],
    console_url   = "https://${aws_mq_broker.main.instances[0].console_url}"
  })
} 