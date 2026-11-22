provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
      Lab       = "2026-11-22-cognito-secure-network-access"
    }
  }
}
