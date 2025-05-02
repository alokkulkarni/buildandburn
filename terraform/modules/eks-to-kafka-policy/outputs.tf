output "policy_arn" {
  description = "ARN of the IAM policy for EKS to Kafka access"
  value       = aws_iam_policy.eks_to_kafka.arn
}

output "policy_name" {
  description = "Name of the IAM policy for EKS to Kafka access"
  value       = aws_iam_policy.eks_to_kafka.name
} 