terraform {
  required_version = ">= 1.6.0"

  required_providers {
    netbox = {
      source  = "e-breuninger/netbox"
      version = "~> 6.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}
