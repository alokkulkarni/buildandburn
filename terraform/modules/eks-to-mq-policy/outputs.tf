output "policy_arn" {
  description = "ARN of the created IAM policy"
  value       = aws_iam_policy.eks_to_mq.arn
}

output "policy_name" {
  description = "Name of the created IAM policy"
  value       = aws_iam_policy.eks_to_mq.name
}

output "policy_attachment_id" {
  description = "ID of the policy attachment"
  value       = aws_iam_role_policy_attachment.attach_eks_to_mq.id
} 