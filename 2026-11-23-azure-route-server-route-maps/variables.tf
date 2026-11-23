variable "location" {
  description = "Azure region for the hub100 hybrid routing lab."
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Resource group name."
  type        = string
  default     = "rg-ars-routemaps-lab"
}

variable "admin_username" {
  description = "Admin username for the Linux NVA and workload VMs."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key" {
  description = "SSH public key for the Linux NVA and workload VMs."
  type        = string
}

variable "vpn_shared_key" {
  description = "IPsec pre-shared key for the lab site-to-site VPN connections."
  type        = string
  sensitive   = true
}

variable "onprem_prefix" {
  description = "On-premises site20 prefix advertised over all hybrid paths."
  type        = string
  default     = "10.20.0.0/24"
}

variable "onprem_asn" {
  description = "On-premises site20 BGP ASN."
  type        = number
  default     = 65020
}

variable "nva_asn" {
  description = "BGP ASN used by nva100-1 and nva100-2."
  type        = number
  default     = 100
}

variable "onprem_peer1_public_ip" {
  description = "RFC 5737 placeholder public IP for on-prem VPN peer 1 (replace with your lab peer)."
  type        = string
  default     = "198.51.100.11"
}

variable "onprem_peer2_public_ip" {
  description = "RFC 5737 placeholder public IP for on-prem VPN peer 2 (replace with your lab peer)."
  type        = string
  default     = "198.51.100.12"
}

variable "enable_expressroute_gateway" {
  description = "Set true to deploy the ExpressRoute gateway (er-gw) alongside vpn-gw and NVAs."
  type        = bool
  default     = false
}
