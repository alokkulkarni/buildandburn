output "policy_arn" {
  description = "ARN of the IAM policy for full Kafka access"
  value       = aws_iam_policy.kafka_full_access.arn
}

output "policy_name" {
  description = "Name of the IAM policy for full Kafka access"
  value       = aws_iam_policy.kafka_full_access.name
} 