locals {
  policy_name = "${var.project_name}-${var.env_id}-mq-full-access-policy"
}

# Create IAM policy for full Amazon MQ access
resource "aws_iam_policy" "mq_full_access" {
  name        = local.policy_name
  description = "IAM policy allowing full access to Amazon MQ resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "mq:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:CreateSecret",
          "secretsmanager:UpdateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:TagResource"
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
resource "aws_iam_role_policy_attachment" "attach_mq_full_access" {
  policy_arn = aws_iam_policy.mq_full_access.arn
  role       = var.node_role_name
} 