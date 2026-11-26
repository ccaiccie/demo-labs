# Toggle which cloud path(s) to deploy in Terraform
variable "enable_aws" {
  description = "Set true to deploy the AWS Verified Access comparison path."
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Set true to deploy the Google Cloud IAP comparison path."
  type        = bool
  default     = false
}

# --- AWS Verified Access Inputs ---
variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "aws_application_domain" {
  type    = string
  default = "app.example.com"
}

variable "aws_acm_cert_arn" {
  type    = string
  default = ""
}

variable "aws_internal_alb_arn" {
  type    = string
  default = ""
}

variable "aws_subnet_ids" {
  type    = list(string)
  default = []
}

variable "aws_security_group_ids" {
  type    = list(string)
  default = []
}

variable "aws_idc_group_id" {
  type    = string
  default = ""
}

# --- Google Cloud IAP Inputs ---
variable "gcp_project_id" {
  type    = string
  default = "your-gcp-project-id"
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

variable "gcp_zone" {
  type    = string
  default = "us-central1-a"
}

variable "gcp_user_member" {
  type    = string
  default = "user:mike@example.com"
}
