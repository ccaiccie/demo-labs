output "netbox_site" {
  description = "Created NetBox site"
  value = {
    id   = netbox_site.branch_dc.id
    name = netbox_site.branch_dc.name
    slug = netbox_site.branch_dc.slug
  }
}

output "netbox_prefixes" {
  description = "Prefixes managed in NetBox"
  value       = { for k, p in netbox_prefix.prefixes : k => p.prefix }
}

output "firewall_interfaces" {
  description = "Firewall interfaces and gateway IPs from NetBox"
  value = {
    for k, obj in local.address_objects : obj.iface_name => {
      zone        = obj.zone
      vlan_id     = obj.vlan_id
      gateway_ip  = obj.gateway_ip
      prefix      = obj.cidr
      description = obj.description
    }
  }
}

output "generated_configs" {
  description = "Standardized firewall configuration files rendered from NetBox"
  value = {
    nftables  = local_file.nftables_config.filename
    vyos      = local_file.vyos_config.filename
    fortigate = local_file.fortigate_config.filename
  }
}
