output "policy_arn" {
  description = "ARN of the IAM policy"
  value       = aws_iam_policy.mq_full_access.arn
}

output "policy_name" {
  description = "Name of the IAM policy"
  value       = aws_iam_policy.mq_full_access.name
} 