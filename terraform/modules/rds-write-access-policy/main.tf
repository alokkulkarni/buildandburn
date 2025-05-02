locals {
  policy_name = "${var.project_name}-${var.env_id}-rds-write-access-policy"
}

# Create IAM policy for limited write access to RDS
resource "aws_iam_policy" "rds_write_access" {
  name        = local.policy_name
  description = "IAM policy allowing write access to RDS resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:DescribeDBProxies",
          "rds:ModifyDBInstance",
          "rds:ModifyDBCluster",
          "rds:RebootDBInstance",
          "rds:CreateDBSnapshot",
          "rds:RestoreDBInstanceFromDBSnapshot",
          "rds:RestoreDBClusterFromSnapshot"
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
resource "aws_iam_role_policy_attachment" "attach_rds_write_access" {
  policy_arn = aws_iam_policy.rds_write_access.arn
  role       = var.node_role_name
} 