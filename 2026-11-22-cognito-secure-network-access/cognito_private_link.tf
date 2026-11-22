# -----------------------------------------------------------------------------
# Domain-Less Cognito User Pool + Interface VPC Endpoints (AWS PrivateLink)
# -----------------------------------------------------------------------------
# AWS PrivateLink honesty:
#   - User pools that have a domain assigned are INCOMPATIBLE with PrivateLink:
#     the existence of a domain prevents completion of user-pool requests that
#     transit a VPC endpoint.
#   - Managed login, classic hosted UI, and OAuth 2.0 client credentials via
#     the token endpoint are NOT supported through PrivateLink.
#   - Supported through PrivateLink: direct SDK/REST API operations
#     (InitiateAuth, AdminInitiateAuth, ListUserPools, etc.), machine-to-machine
#     authorization via GetClientToken (no domain required), and Identity Pool
#     SDK/REST API calls.
#   - Private DNS routes cognito-idp.<region>.amazonaws.com and
#     cognito-identity.<region>.amazonaws.com to the endpoint ENIs; it does NOT
#     route user-pool domain hostnames (*.auth.<region>.amazoncognito.com).
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "private_api" {
  name           = "${var.project_name}-private-api-pool"
  user_pool_tier = "ESSENTIALS"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  # INTENTIONALLY NO aws_cognito_user_pool_domain resource for this pool.
  tags = {
    Purpose = "Domain-less pool for AWS PrivateLink direct API and GetClientToken M2M"
  }
}

resource "aws_cognito_user_pool_client" "private_m2m" {
  name         = "${var.project_name}-private-api-client"
  user_pool_id = aws_cognito_user_pool.private_api.id

  generate_secret               = true
  prevent_user_existence_errors = "ENABLED"

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]
}

# Interface VPC Endpoint for Amazon Cognito User Pools API (cognito-idp)
resource "aws_vpc_endpoint" "cognito_idp" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.cognito-idp"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpce.id]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCognitoIdpForPrivateLabPool"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "cognito-idp:DescribeUserPool",
          "cognito-idp:InitiateAuth",
          "cognito-idp:RespondToAuthChallenge",
          "cognito-idp:AdminInitiateAuth",
          "cognito-idp:AdminRespondToAuthChallenge",
          "cognito-idp:GetClientToken"
        ]
        Resource = aws_cognito_user_pool.private_api.arn
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-cognito-idp-vpce"
  }
}

# Interface VPC Endpoint for Amazon Cognito Identity Pools API (cognito-identity)
resource "aws_vpc_endpoint" "cognito_identity" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.cognito-identity"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpce.id]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCognitoIdentityForLabPool"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "cognito-identity:GetId",
          "cognito-identity:GetCredentialsForIdentity",
          "cognito-identity:GetOpenIdToken"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-cognito-identity-vpce"
  }
}
