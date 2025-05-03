output "policy_arn" {
  description = "The ARN of the created IAM policy"
  value       = aws_iam_policy.eks_to_ecr.arn
}

output "policy_name" {
  description = "The name of the created IAM policy"
  value       = aws_iam_policy.eks_to_ecr.name
} 