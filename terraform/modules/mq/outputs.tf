output "mq_id" {
  description = "ID of the message broker"
  value       = aws_mq_broker.main.id
}

output "mq_endpoint" {
  description = "Endpoint of the message broker"
  value       = aws_mq_broker.main.instances[0].endpoints[0]
}

output "mq_username" {
  description = "Username for the message broker"
  value       = local.mq_username
  sensitive   = true
}

output "mq_password" {
  description = "Password for the message broker"
  value       = local.mq_password
  sensitive   = true
}

output "mq_console_url" {
  description = "Console URL for the message broker"
  value       = "https://${aws_mq_broker.main.instances[0].console_url}"
}

output "mq_secret_arn" {
  description = "ARN of the secret containing message broker credentials"
  value       = aws_secretsmanager_secret.mq_credentials.arn
} 