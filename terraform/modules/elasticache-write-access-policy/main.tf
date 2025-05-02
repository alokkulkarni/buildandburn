locals {
  policy_name = "${var.project_name}-${var.env_id}-elasticache-write-access-policy"
}

# Create IAM policy for limited write access to ElastiCache
resource "aws_iam_policy" "elasticache_write_access" {
  name        = local.policy_name
  description = "IAM policy allowing write access to ElastiCache resources"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeReplicationGroups",
          "elasticache:DescribeCacheParameterGroups",
          "elasticache:ModifyCacheCluster",
          "elasticache:ModifyReplicationGroup",
          "elasticache:RebootCacheCluster",
          "elasticache:CreateSnapshot",
          "elasticache:RestoreCacheClusterFromSnapshot"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:UpdateSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}-${var.env_id}-redis-*"
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
resource "aws_iam_role_policy_attachment" "attach_elasticache_write_access" {
  policy_arn = aws_iam_policy.elasticache_write_access.arn
  role       = var.node_role_name
} 