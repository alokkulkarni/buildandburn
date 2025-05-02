locals {
  policy_name = "${var.project_name}-${var.env_id}-mq-write-access-policy"
}

# Create IAM policy for limited write access to Amazon MQ
resource "aws_iam_policy" "mq_write_access" {
  name        = local.policy_name
  description = "IAM policy allowing write access to Amazon MQ resources"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "mq:DescribeBroker",
          "mq:DescribeBrokerEngineTypes",
          "mq:DescribeBrokerInstanceOptions",
          "mq:UpdateBroker",
          "mq:RebootBroker",
          "mq:CreateConfiguration",
          "mq:UpdateConfiguration",
          "mq:ListConfigurations",
          "mq:DescribeConfiguration",
          "mq:DescribeConfigurationRevision",
          "mq:CreateUser",
          "mq:DeleteUser",
          "mq:UpdateUser",
          "mq:ListUsers"
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
resource "aws_iam_role_policy_attachment" "attach_mq_write_access" {
  policy_arn = aws_iam_policy.mq_write_access.arn
  role       = var.node_role_name
} 