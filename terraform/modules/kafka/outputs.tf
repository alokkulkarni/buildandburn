output "kafka_arn" {
  description = "ARN of the MSK cluster"
  value       = aws_msk_cluster.main.arn
}

output "kafka_bootstrap_brokers" {
  description = "Connection host:port pairs for the MSK cluster"
  value       = aws_msk_cluster.main.bootstrap_brokers
}

output "kafka_bootstrap_brokers_tls" {
  description = "TLS Connection host:port pairs for the MSK cluster"
  value       = aws_msk_cluster.main.bootstrap_brokers_tls
}

output "kafka_bootstrap_brokers_sasl_scram" {
  description = "SASL SCRAM Connection host:port pairs for the MSK cluster"
  value       = aws_msk_cluster.main.bootstrap_brokers_sasl_scram
}

output "kafka_zookeeper_connect_string" {
  description = "Zookeeper connection string for the MSK cluster"
  value       = aws_msk_cluster.main.zookeeper_connect_string
}

output "kafka_secret_arn" {
  description = "ARN of the secret containing Kafka configuration"
  value       = aws_secretsmanager_secret.kafka_config.arn
}

output "kafka_configuration_arn" {
  description = "ARN of the MSK configuration"
  value       = aws_msk_configuration.main.arn
}

output "kafka_security_group_id" {
  description = "ID of the Kafka security group"
  value       = aws_security_group.kafka.id
} 