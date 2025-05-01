locals {
  policy_name = "${var.project_name}-${var.env_id}-eks-to-mq-policy"
}

# Create IAM policy for EKS to MQ access
resource "aws_iam_policy" "eks_to_mq" {
  name        = local.policy_name
  description = "IAM policy allowing EKS nodes to access Amazon MQ and retrieve broker credentials"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "mq:DescribeBroker",
          "mq:ListBrokers"
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
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}-${var.env_id}-mq-*"
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
resource "aws_iam_role_policy_attachment" "attach_eks_to_mq" {
  policy_arn = aws_iam_policy.eks_to_mq.arn
  role       = var.node_role_name
} 