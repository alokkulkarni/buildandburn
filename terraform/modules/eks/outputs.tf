output "cluster_id" {
  description = "The ID of the EKS cluster"
  value       = aws_eks_cluster.main.id
}

output "cluster_name" {
  description = "The name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "The ARN of the EKS cluster"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "The endpoint URL for the EKS cluster"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_certificate_authority_data" {
  description = "The certificate authority data for the EKS cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "The security group ID for the EKS cluster"
  value       = aws_security_group.cluster.id
}

output "kubeconfig" {
  description = "The kubeconfig file for the EKS cluster"
  value       = local.kubeconfig
  sensitive   = true
}

output "node_group_id" {
  description = "The ID of the EKS node group"
  value       = aws_eks_node_group.main.id
}

output "node_role_name" {
  description = "The name of the EKS node IAM role"
  value       = aws_iam_role.node_group.name
}

output "node_role_arn" {
  description = "The ARN of the EKS node IAM role"
  value       = aws_iam_role.node_group.arn
} 