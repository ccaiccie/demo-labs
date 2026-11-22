# -----------------------------------------------------------------------------
# API Gateway REST API with Amazon Cognito User Pool Authorizer
# -----------------------------------------------------------------------------
# Token validation behavior:
#   - With NO `authorization_scopes` on the method, API Gateway validates a
#     Cognito ID token in the `Authorization` header.
#   - If you add `authorization_scopes`, API Gateway validates a Cognito access
#     token against those scopes instead.
#   - When a Regional AWS WAFv2 Web ACL is associated with the API stage (see
#     waf.tf), AWS WAF is evaluated BEFORE the Cognito authorizer.
# -----------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project_name}-rest-api"
  description = "Regional REST API protected by a Cognito User Pool authorizer and AWS WAFv2"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${var.project_name}-cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.public_edge.arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_resource" "protected" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "protected"
}

resource "aws_api_gateway_method" "protected_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.protected.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

# MOCK integration returns a 200 JSON payload immediately after Cognito token
# validation so the endpoint can be tested without deploying a backend Lambda.
resource "aws_api_gateway_integration" "protected_mock" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.protected.id
  http_method = aws_api_gateway_method.protected_get.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "protected_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.protected.id
  http_method = aws_api_gateway_method.protected_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "protected_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.protected.id
  http_method = aws_api_gateway_method.protected_get.http_method
  status_code = aws_api_gateway_method_response.protected_200.status_code

  response_templates = {
    "application/json" = jsonencode({
      message = "Authorized by Amazon Cognito User Pool authorizer"
    })
  }

  depends_on = [aws_api_gateway_integration.protected_mock]
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_authorizer.cognito.id,
      aws_api_gateway_resource.protected.id,
      aws_api_gateway_method.protected_get.id,
      aws_api_gateway_integration.protected_mock.id,
      aws_api_gateway_integration_response.protected_200.id
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "v1"
}
