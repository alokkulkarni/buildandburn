provider "aws" {
  region = var.region

  # Retry configuration
  max_retries = 15

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Project     = var.project_name
      Environment = "buildandburn-${var.env_id}"
    }
  }
} 