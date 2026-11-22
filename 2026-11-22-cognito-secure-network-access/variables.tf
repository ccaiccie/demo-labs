variable "aws_region" {
  description = "AWS Region where the lab resources will be deployed."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short prefix applied to resource names and tags."
  type        = string
  default     = "cognito-net-lab"
}

variable "vpc_cidr" {
  description = "CIDR block for the lab VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zones" {
  description = "Two Availability Zones in the chosen AWS Region for public and private subnets."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Provide exactly two Availability Zones."
  }
}

variable "cognito_domain_prefix" {
  description = "Globally unique Amazon Cognito domain prefix for the public-edge user pool (lowercase letters, numbers, hyphens)."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of a pre-validated AWS Certificate Manager (ACM) certificate in the same Region for the HTTPS ALB listener."
  type        = string
}

variable "alb_fqdn" {
  description = "Optional custom DNS name (CNAME/Alias) pointing to the ALB, added to Cognito callback URLs. Leave empty to use only the ALB DNS name."
  type        = string
  default     = ""
}

variable "alb_internal" {
  description = "Set to true to deploy an internal ALB in private subnets (relying on the NAT Gateway for outbound IPv4 calls to Cognito's token and user-info endpoints). Default false deploys an internet-facing ALB in public subnets."
  type        = bool
  default     = false
}

variable "alb_ingress_cidrs" {
  description = "CIDR blocks permitted to reach the ALB on HTTPS (443) and HTTP (80 redirect). Restrict to your own IP range in practice."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "waf_rate_limit" {
  description = "AWS WAFv2 IP rate-based rule threshold per 5-minute window (minimum 10 in AWS WAFv2)."
  type        = number
  default     = 1000
}

variable "enable_waf_on_alb" {
  description = "Associate the Regional WAFv2 Web ACL with the Application Load Balancer in addition to the public-edge Cognito User Pool."
  type        = bool
  default     = true
}

variable "enable_waf_on_apigw" {
  description = "Associate the Regional WAFv2 Web ACL with the API Gateway REST API stage in addition to the public-edge Cognito User Pool."
  type        = bool
  default     = true
}
