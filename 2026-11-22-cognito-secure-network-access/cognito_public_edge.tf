# -----------------------------------------------------------------------------
# Public-Edge Amazon Cognito User Pool (WITH User Pool Domain)
# -----------------------------------------------------------------------------
# Used for:
#   1. Application Load Balancer HTTPS `authenticate-cognito` (Managed Login)
#   2. API Gateway REST API `COGNITO_USER_POOLS` authorizer
#   3. AWS WAFv2 Regional Web ACL protection on the user pool
#
# IMPORTANT: Because this pool has a user pool domain attached (required for
# ALB authenticate-cognito and Managed Login), it is INCOMPATIBLE with AWS
# PrivateLink interface VPC endpoints. See cognito_private_link.tf for the
# separate domain-less pool used to demonstrate PrivateLink honestly.
# -----------------------------------------------------------------------------

locals {
  alb_callback_urls = compact([
    "https://${aws_lb.app.dns_name}/oauth2/idpresponse",
    var.alb_fqdn != "" ? "https://${var.alb_fqdn}/oauth2/idpresponse" : ""
  ])
}

resource "aws_cognito_user_pool" "public_edge" {
  name           = "${var.project_name}-public-edge-pool"
  user_pool_tier = "ESSENTIALS" # Ready for Essentials-tier features (ACR target levels, RFC 8693 token exchange, MRR)

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Purpose = "Public-edge ALB and API Gateway authentication (has domain; not for PrivateLink)"
  }
}

resource "aws_cognito_user_pool_domain" "public_edge" {
  domain                = var.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.public_edge.id
  managed_login_version = 2 # 2 = Managed Login (1 = Classic Hosted UI)
}

# App Client for ALB authenticate-cognito:
# - MUST have generate_secret = true
# - MUST use authorization code grant ("code")
# - MUST include the same OAuth scopes configured on the ALB HTTPS listener
#
# Provider gap note (hashicorp/aws v6.73.0):
# Managed secret storage/rotation in AWS Secrets Manager
# (PublishSecretsInAWSSecretsManager, launched Nov 19, 2026) is not yet exposed
# in aws_cognito_user_pool_client. See README.md for AWS CLI / CloudFormation steps.
resource "aws_cognito_user_pool_client" "alb" {
  name         = "${var.project_name}-alb-client"
  user_pool_id = aws_cognito_user_pool.public_edge.id

  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = local.alb_callback_urls
  prevent_user_existence_errors        = "ENABLED"

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  depends_on = [aws_cognito_user_pool_domain.public_edge]
}

# Public App Client for API Gateway & Identity Pool CLI testing
resource "aws_cognito_user_pool_client" "api" {
  name         = "${var.project_name}-api-client"
  user_pool_id = aws_cognito_user_pool.public_edge.id

  generate_secret               = false
  prevent_user_existence_errors = "ENABLED"

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]
}
