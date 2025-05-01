locals {
  policy_name = "${var.project_name}-${var.env_id}-eks-to-elasticache-policy"
}

# Create IAM policy for EKS to ElastiCache access
resource "aws_iam_policy" "eks_to_elasticache" {
  name        = local.policy_name
  description = "IAM policy allowing EKS nodes to access Amazon ElastiCache and retrieve cache information"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeReplicationGroups",
          "elasticache:DescribeCacheParameterGroups",
          "elasticache:DescribeCacheParameters",
          "elasticache:DescribeCacheSubnetGroups",
          "elasticache:DescribeEngineDefaultParameters",
          "elasticache:ListTagsForResource",
          "elasticache:ListAllowedNodeTypeModifications"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecretVersionIds"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}-${var.env_id}-cache-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService": "secretsmanager.${var.region}.amazonaws.com"
          }
        }
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
resource "aws_iam_role_policy_attachment" "attach_eks_to_elasticache" {
  policy_arn = aws_iam_policy.eks_to_elasticache.arn
  role       = var.node_role_name
} 