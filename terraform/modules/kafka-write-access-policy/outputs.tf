output "policy_arn" {
  description = "ARN of the IAM policy for write access to Kafka"
  value       = aws_iam_policy.kafka_write_access.arn
}

output "policy_name" {
  description = "Name of the IAM policy for write access to Kafka"
  value       = aws_iam_policy.kafka_write_access.name
} 