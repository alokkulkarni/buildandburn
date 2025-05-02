locals {
  policy_name = "${var.project_name}-${var.env_id}-eks-to-kafka-policy"
}

# Create IAM policy for EKS to Kafka access
resource "aws_iam_policy" "eks_to_kafka" {
  name        = local.policy_name
  description = "IAM policy allowing EKS nodes to access Amazon MSK (Kafka) and retrieve cluster configuration"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka:DescribeCluster",
          "kafka:GetBootstrapBrokers",
          "kafka:ListClusters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka:DescribeConfiguration",
          "kafka:DescribeConfigurationRevision",
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
          "cloudwatch:ListMetrics"
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
resource "aws_iam_role_policy_attachment" "attach_eks_to_kafka" {
  policy_arn = aws_iam_policy.eks_to_kafka.arn
  role       = var.node_role_name
} 