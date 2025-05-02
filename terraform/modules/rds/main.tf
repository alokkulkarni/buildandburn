locals {
  # Ensure db_name only contains alphanumeric characters and starts with a letter
  db_name     = replace("db${var.project_name}${var.env_id}", "/[^a-zA-Z0-9]/", "")
  db_username = "bbadmin"
  db_password = random_password.db_password.result
}

# Generate a random password for the database
resource "random_password" "db_password" {
  length  = 16
  special = false
}

# Security group for the database
resource "aws_security_group" "db" {
  name        = "${var.project_name}-${var.env_id}-db-sg"
  description = "Security group for RDS instance"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    description     = "Allow PostgreSQL traffic"
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
      Name = "${var.project_name}-${var.env_id}-db-sg"
    }
  )
}

# Subnet group for the database
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.env_id}-db-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-db-subnet-group"
    }
  )
}

# Parameter group for the database
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-${var.env_id}-db-params"
  family = "${var.engine}${var.engine_version}"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-db-params"
    }
  )
}

# RDS instance
resource "aws_db_instance" "main" {
  identifier        = "${var.project_name}-${var.env_id}-db"
  engine            = var.engine
  engine_version    = var.engine_version
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp2"

  db_name  = local.db_name
  username = local.db_username
  password = local.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false

  # Add extended timeouts
  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-db"
    }
  )
}

# Store database credentials in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}-${var.env_id}-db-credentials"
  description = "Database credentials for build-and-burn environment"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = local.db_username,
    password = local.db_password,
    engine   = var.engine,
    host     = aws_db_instance.main.address,
    port     = aws_db_instance.main.port,
    dbname   = local.db_name
  })
} 