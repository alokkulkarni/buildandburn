locals {
  policy_name = "${var.project_name}-${var.env_id}-eks-to-rds-policy"
}

# Create IAM policy for EKS to RDS access
resource "aws_iam_policy" "eks_to_rds" {
  name        = local.policy_name
  description = "IAM policy allowing EKS nodes to access RDS and retrieve database credentials"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:DescribeDBProxies"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}-${var.env_id}-db-*"
        ]
      }
    ]
  })
  
  tags = merge(
    var.tags,
    {
      Name = local.policy_name
    }
  )
}

# Attach the policy to the node group role
resource "aws_iam_role_policy_attachment" "attach_eks_to_rds" {
  policy_arn = aws_iam_policy.eks_to_rds.arn
  role       = var.node_role_name
} 