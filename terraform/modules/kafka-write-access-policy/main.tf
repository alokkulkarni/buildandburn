locals {
  policy_name = "${var.project_name}-${var.env_id}-kafka-write-access-policy"
}

# Create IAM policy for write access to Kafka
resource "aws_iam_policy" "kafka_write_access" {
  name        = local.policy_name
  description = "IAM policy allowing write access to Amazon MSK (Kafka) for the project"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka:GetBootstrapBrokers",
          "kafka:DescribeCluster",
          "kafka:DescribeConfiguration",
          "kafka:DescribeConfigurationRevision",
          "kafka:ListClusters",
          "kafka:ListConfigurations"
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
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}-${var.env_id}-kafka-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics",
          "cloudwatch:GetMetricStatistics"
        ],
        Resource = "*"
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
resource "aws_iam_role_policy_attachment" "attach_kafka_write_access" {
  policy_arn = aws_iam_policy.kafka_write_access.arn
  role       = var.node_role_name
} 