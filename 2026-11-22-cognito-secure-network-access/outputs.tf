output "vpc_id" {
  description = "ID of the lab VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs."
  value       = aws_subnet.private[*].id
}

output "nat_gateway_public_ip" {
  description = "Elastic IP attached to the NAT Gateway (used by private subnets / internal ALB for outbound IPv4 traffic)."
  value       = aws_eip.nat.public_ip
}

output "public_edge_user_pool_id" {
  description = "ID of the public-edge Cognito User Pool (has domain; used by ALB and API Gateway)."
  value       = aws_cognito_user_pool.public_edge.id
}

output "public_edge_user_pool_arn" {
  description = "ARN of the public-edge Cognito User Pool."
  value       = aws_cognito_user_pool.public_edge.arn
}

output "public_edge_user_pool_domain" {
  description = "Managed Login domain prefix for the public-edge Cognito User Pool."
  value       = aws_cognito_user_pool_domain.public_edge.domain
}

output "alb_app_client_id" {
  description = "Cognito App Client ID configured for ALB authenticate-cognito."
  value       = aws_cognito_user_pool_client.alb.id
}

output "api_app_client_id" {
  description = "Public Cognito App Client ID for API Gateway and Identity Pool CLI testing."
  value       = aws_cognito_user_pool_client.api.id
}

output "private_api_user_pool_id" {
  description = "ID of the separate domain-less Cognito User Pool for AWS PrivateLink."
  value       = aws_cognito_user_pool.private_api.id
}

output "private_api_app_client_id" {
  description = "App Client ID on the domain-less PrivateLink user pool."
  value       = aws_cognito_user_pool_client.private_m2m.id
}

output "identity_pool_id" {
  description = "ID of the Cognito Identity Pool (exchanges User Pool tokens for temporary AWS STS credentials)."
  value       = aws_cognito_identity_pool.main.id
}

output "alb_dns_name" {
  description = "DNS name of the HTTPS Application Load Balancer."
  value       = aws_lb.app.dns_name
}

output "api_gateway_protected_url" {
  description = "Invoke URL for the Cognito-authorized GET /protected endpoint."
  value       = "${aws_api_gateway_stage.prod.invoke_url}/protected"
}

output "waf_web_acl_arn" {
  description = "ARN of the Regional AWS WAFv2 Web ACL."
  value       = aws_wafv2_web_acl.cognito_edge.arn
}

output "cognito_idp_vpc_endpoint_id" {
  description = "Interface VPC Endpoint ID for com.amazonaws.<region>.cognito-idp."
  value       = aws_vpc_endpoint.cognito_idp.id
}

output "cognito_identity_vpc_endpoint_id" {
  description = "Interface VPC Endpoint ID for com.amazonaws.<region>.cognito-identity."
  value       = aws_vpc_endpoint.cognito_identity.id
}
