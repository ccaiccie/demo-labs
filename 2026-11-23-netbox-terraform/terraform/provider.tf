provider "netbox" {
  # Reads NETBOX_SERVER_URL and NETBOX_API_TOKEN from environment variables
  # so credentials are never hardcoded in Terraform files.
  skip_version_check = true
}
