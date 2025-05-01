output "db_instance_id" {
  description = "ID of the database instance"
  value       = aws_db_instance.main.id
}

output "db_endpoint" {
  description = "Endpoint of the database"
  value       = aws_db_instance.main.endpoint
}

output "db_username" {
  description = "Username for the database"
  value       = local.db_username
  sensitive   = true
}

output "db_password" {
  description = "Password for the database"
  value       = local.db_password
  sensitive   = true
}

output "db_name" {
  description = "Name of the database"
  value       = local.db_name
}

output "db_port" {
  description = "Port of the database"
  value       = aws_db_instance.main.port
}

output "db_secret_arn" {
  description = "ARN of the secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
} 