# -----------------------------------------------------------------------------
# Amazon Cognito Identity Pool (Contrast with User Pools)
# -----------------------------------------------------------------------------
# User Pool     = Sign-up / sign-in directory that issues JWTs (ID, Access,
#                 Refresh tokens) for your application.
# Identity Pool = Exchanges an identity (such as a User Pool ID token) for
#                 temporary AWS STS credentials via an IAM role so clients can
#                 call AWS services directly.
# -----------------------------------------------------------------------------

resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = replace("${var.project_name}_identity_pool", "-", "_")
  allow_unauthenticated_identities = false
  allow_classic_flow               = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.api.id
    provider_name           = aws_cognito_user_pool.public_edge.endpoint
    server_side_token_check = true
  }
}

resource "aws_iam_role" "cognito_authenticated" {
  name = "${var.project_name}-cognito-auth-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })
}

# Minimal, read-only example policy demonstrating least-privilege AWS access
# granted by the Identity Pool's temporary STS credentials.
resource "aws_iam_role_policy" "cognito_authenticated_minimal" {
  name = "${var.project_name}-cognito-auth-policy"
  role = aws_iam_role.cognito_authenticated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ExampleScopedS3ReadOnly"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${var.project_name}-example-assets/public/*"
      }
    ]
  })
}

resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    authenticated = aws_iam_role.cognito_authenticated.arn
  }
}
