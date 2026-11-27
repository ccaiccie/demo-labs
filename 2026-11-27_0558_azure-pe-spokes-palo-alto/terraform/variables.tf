variable "subscription_id" {
  description = "Azure subscription to deploy the lab into."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westus2"
}

variable "prefix" {
  description = "Short name prefix for every resource."
  type        = string
  default     = "pespoke"
}

variable "admin_username" {
  description = "Admin user for the VM-Series and the Linux test VMs."
  type        = string
  default     = "labadmin"
}

variable "fw_admin_password" {
  description = "VM-Series admin password (web UI and SSH). Must meet PAN-OS complexity rules."
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for the Linux test VMs (they have no public IP; use Run Command or Bastion)."
  type        = string
}

variable "mgmt_allowed_cidr" {
  description = "Your public IP in CIDR form, allowed to reach the VM-Series management interface on 443 and 22."
  type        = string
}

variable "fw_vm_size" {
  description = "VM size for the VM-Series (3 NICs needed)."
  type        = string
  default     = "Standard_D3_v2"
}

variable "fw_sku" {
  description = "VM-Series marketplace plan: byol, bundle1 or bundle2. Accept the terms first: az vm image terms accept --publisher paloaltonetworks --offer vmseries-flex --plan <sku>"
  type        = string
  default     = "bundle1"
}

variable "fw_version" {
  description = "PAN-OS image version, or latest."
  type        = string
  default     = "latest"
}

variable "steer_through_firewall" {
  description = "true = create the UDRs that force private endpoint traffic through the firewall. false = baseline, traffic bypasses the firewall. Flip it to compare."
  type        = bool
  default     = true
}

variable "snat_mode" {
  description = "How return traffic from private endpoints stays symmetric: firewall_snat (PAN-OS source NAT to the trust interface) or disable_snat_on_pl (NIC tag, client IP preserved)."
  type        = string
  default     = "firewall_snat"
  validation {
    condition     = contains(["firewall_snat", "disable_snat_on_pl"], var.snat_mode)
    error_message = "snat_mode must be firewall_snat or disable_snat_on_pl."
  }
}

variable "lock_pe_subnets_with_nsg" {
  description = "Attach an NSG to each private endpoint subnet that only allows HTTPS from the firewall path (and denies other VNet sources)."
  type        = bool
  default     = true
}

variable "test_vm_size" {
  description = "VM size for the Linux test clients."
  type        = string
  default     = "Standard_B1s"
}
