# Comparable Path 1: AWS Verified Access (IAM Identity Center + Cedar Policy + Browser, No VPN)

resource "aws_verifiedaccess_trust_provider" "idc" {
  count                    = var.enable_aws ? 1 : 0
  description              = "Multicloud lab IAM Identity Center trust provider"
  policy_reference_name    = "idc"
  trust_provider_type      = "user"
  user_trust_provider_type = "iam-identity-center"
}

resource "aws_verifiedaccess_instance" "main" {
  count       = var.enable_aws ? 1 : 0
  description = "Multicloud lab Verified Access instance"
}

resource "aws_verifiedaccess_instance_trust_provider_attachment" "idc" {
  count                            = var.enable_aws ? 1 : 0
  verifiedaccess_instance_id       = aws_verifiedaccess_instance.main[0].id
  verifiedaccess_trust_provider_id = aws_verifiedaccess_trust_provider.idc[0].id
}

resource "aws_verifiedaccess_group" "app" {
  count                      = var.enable_aws ? 1 : 0
  verifiedaccess_instance_id = aws_verifiedaccess_instance.main[0].id
  description                = "Multicloud lab Cedar policy group"
  policy_document            = <<-EOT
    permit(principal, action, resource)
    when {
      context.idc.groups has "${var.aws_idc_group_id}"
      && context.idc.user.email.verified == true
    };
  EOT

  depends_on = [aws_verifiedaccess_instance_trust_provider_attachment.idc]
}

resource "aws_verifiedaccess_endpoint" "alb" {
  count                    = var.enable_aws ? 1 : 0
  verified_access_group_id = aws_verifiedaccess_group.app[0].id
  attachment_type          = "vpc"
  endpoint_type            = "load-balancer"
  application_domain       = var.aws_application_domain
  domain_certificate_arn   = var.aws_acm_cert_arn
  endpoint_domain_prefix   = "mc-ava-lab"
  security_group_ids       = var.aws_security_group_ids

  load_balancer_options {
    load_balancer_arn = var.aws_internal_alb_arn
    port              = 443
    protocol          = "https"
    subnet_ids        = var.aws_subnet_ids
  }
}
