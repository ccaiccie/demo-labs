# -----------------------------------------------------------------------------
# AWS WAFv2 Regional Web ACL & Associations (Cognito User Pool, ALB, API GW)
# -----------------------------------------------------------------------------
# What AWS WAF CAN and CANNOT see on Amazon Cognito User Pools:
#   - Cognito forwards only selected non-confidential headers and metadata.
#   - NO PII: Usernames, passwords, email addresses, and phone numbers are NOT
#     available to WAF; do not write WAF rules that expect to match PII.
#   - NO REQUEST BODY on Managed Login / Classic Hosted UI: Body-based WAF
#     inspection works only on Cognito user-pool API requests, not on Managed
#     Login or Classic Hosted UI pages.
#   - Evaluation order on Cognito: WAF runs BEFORE Cognito API-level throttling
#     (blocked requests do not consume Cognito request rate quotas).
#   - Incompatible rule group: `AWS-AWSManagedRulesATPRuleSet` (Fraud Control
#     ATP) CANNOT be included in a Web ACL associated with a Cognito User Pool.
#   - Evaluation order on API Gateway: WAF runs BEFORE the Cognito authorizer
#     (and inspects headers, method, query string, URI, and first 64 KB body).
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "cognito_edge" {
  name        = "${var.project_name}-waf-acl"
  description = "Regional WAFv2 Web ACL protecting Cognito User Pool, ALB, and API Gateway stage"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: Source-IP rate limit (relies on network metadata, not PII or body)
  rule {
    name     = "rate-limit-by-ip"
    priority = 10

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-rate-limit-ip"
      sampled_requests_enabled   = true
    }
  }

  # Rule 2: AWS Managed IP Reputation List
  rule {
    name     = "aws-managed-ip-reputation"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  # Rule 3: AWS Managed Common Rule Set
  # Note: On Cognito Managed Login / Hosted UI, request body is not forwarded
  # to WAF, so body-matching sub-rules apply only to Cognito API, ALB, and API GW.
  rule {
    name     = "aws-managed-common-rules"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-waf-acl"
    sampled_requests_enabled   = true
  }
}

# Associate WAFv2 Web ACL with the Public-Edge Cognito User Pool
resource "aws_wafv2_web_acl_association" "cognito_public_edge" {
  resource_arn = aws_cognito_user_pool.public_edge.arn
  web_acl_arn  = aws_wafv2_web_acl.cognito_edge.arn
}

# Optional: Associate the same Regional WAFv2 Web ACL with the ALB
resource "aws_wafv2_web_acl_association" "alb" {
  count        = var.enable_waf_on_alb ? 1 : 0
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.cognito_edge.arn
}

# Optional: Associate the same Regional WAFv2 Web ACL with the API Gateway stage
# Evaluated BEFORE the Cognito User Pool Authorizer.
resource "aws_wafv2_web_acl_association" "apigw_stage" {
  count        = var.enable_waf_on_apigw ? 1 : 0
  resource_arn = aws_api_gateway_stage.prod.arn
  web_acl_arn  = aws_wafv2_web_acl.cognito_edge.arn
}
