locals {
  policy_name = "${var.project_name}-${var.env_id}-eks-to-ecr-policy"
}

# Create IAM policy for EKS to ECR access
resource "aws_iam_policy" "eks_to_ecr" {
  name        = local.policy_name
  description = "IAM policy allowing EKS nodes to access ECR repositories, including cross-account access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      # Add specific cross-account access for any referenced repositories
      # This statement allows access to repositories in any account
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "arn:aws:ecr:*:*:repository/*"
      },
      # Allow the EKS nodes to assume an ECR cross-account role if needed
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = "arn:aws:iam::*:role/*ECR*"
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
resource "aws_iam_role_policy_attachment" "attach_eks_to_ecr" {
  policy_arn = aws_iam_policy.eks_to_ecr.arn
  role       = var.node_role_name
} 