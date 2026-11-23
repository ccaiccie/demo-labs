variable "site_name" {
  description = "Human-readable name of the NetBox site"
  type        = string
  default     = "Branch-West-DC1"
}

variable "site_slug" {
  description = "URL-safe slug for the NetBox site"
  type        = string
  default     = "branch-west-dc1"
}

variable "vlans" {
  description = "Standardized VLANs and RFC 5737 prefixes managed in NetBox"
  type = map(object({
    vid         = number
    name        = string
    prefix      = string
    gateway_ip  = string
    iface_name  = string
    zone        = string
    description = string
  }))
  default = {
    corp_users = {
      vid         = 10
      name        = "CORP-USERS"
      prefix      = "198.51.100.0/24"
      gateway_ip  = "198.51.100.1/24"
      iface_name  = "eth-lan"
      zone        = "LAN"
      description = "Corporate workstation VLAN"
    }
    dmz_web = {
      vid         = 20
      name        = "DMZ-WEB"
      prefix      = "203.0.113.0/24"
      gateway_ip  = "203.0.113.1/24"
      iface_name  = "eth-dmz"
      zone        = "DMZ"
      description = "External-facing web services DMZ"
    }
    mgmt_oob = {
      vid         = 99
      name        = "MGMT-OOB"
      prefix      = "192.0.2.0/24"
      gateway_ip  = "192.0.2.1/24"
      iface_name  = "eth-mgmt"
      zone        = "MGMT"
      description = "Out-of-band network management"
    }
  }
}

variable "firewall_policies" {
  description = "Standardized firewall policies referencing NetBox prefix keys"
  type = list(object({
    id          = number
    name        = string
    src_key     = string
    dst_key     = string
    protocol    = string
    port        = number
    action      = string
    description = string
  }))
  default = [
    {
      id          = 10
      name        = "allow-corp-to-dmz-https"
      src_key     = "corp_users"
      dst_key     = "dmz_web"
      protocol    = "tcp"
      port        = 443
      action      = "accept"
      description = "Allow corporate users HTTPS access to DMZ web servers"
    },
    {
      id          = 20
      name        = "allow-corp-to-dmz-dns"
      src_key     = "corp_users"
      dst_key     = "dmz_web"
      protocol    = "udp"
      port        = 53
      action      = "accept"
      description = "Allow corporate users DNS queries to DMZ resolvers"
    },
    {
      id          = 30
      name        = "allow-mgmt-to-dmz-ssh"
      src_key     = "mgmt_oob"
      dst_key     = "dmz_web"
      protocol    = "tcp"
      port        = 22
      action      = "accept"
      description = "Allow management subnet SSH administration to DMZ hosts"
    },
    {
      id          = 40
      name        = "deny-dmz-to-corp-all"
      src_key     = "dmz_web"
      dst_key     = "corp_users"
      protocol    = "tcp"
      port        = 0
      action      = "drop"
      description = "Explicitly block DMZ hosts from initiating traffic to corporate LAN"
    }
  ]
}
