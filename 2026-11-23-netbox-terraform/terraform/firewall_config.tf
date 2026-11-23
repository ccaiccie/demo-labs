# -----------------------------------------------------------------------------
# Build normalized firewall model directly from NetBox-managed objects
# -----------------------------------------------------------------------------
locals {
  firewall_device = netbox_device.fw_edge_01.name
  site_label      = netbox_site.branch_dc.name

  address_objects = {
    for k, p in netbox_prefix.prefixes : k => {
      name        = "NET_${upper(k)}"
      cidr        = p.prefix
      vlan_id     = netbox_vlan.vlans[k].vid
      vlan_name   = netbox_vlan.vlans[k].name
      iface_name  = netbox_device_interface.fw_zones[k].name
      gateway_ip  = netbox_ip_address.fw_zone_ips[k].ip_address
      zone        = var.vlans[k].zone
      description = netbox_device_interface.fw_zones[k].description
    }
  }

  rendered_policies = [
    for pol in var.firewall_policies : {
      id          = pol.id
      name        = pol.name
      src_obj     = local.address_objects[pol.src_key].name
      src_cidr    = local.address_objects[pol.src_key].cidr
      src_iface   = local.address_objects[pol.src_key].iface_name
      dst_obj     = local.address_objects[pol.dst_key].name
      dst_cidr    = local.address_objects[pol.dst_key].cidr
      dst_iface   = local.address_objects[pol.dst_key].iface_name
      protocol    = pol.protocol
      port        = pol.port
      action      = pol.action
      description = pol.description
    }
  ]

  template_vars = {
    device_name     = local.firewall_device
    site_name       = local.site_label
    address_objects = local.address_objects
    policies        = local.rendered_policies
  }
}

# 1. Live Linux nftables firewall ruleset (applied to nb-tf-fw-edge-01)
resource "local_file" "nftables_config" {
  filename = "${path.module}/generated/fw-edge-01.nft"
  content  = templatefile("${path.module}/templates/nftables.tftpl", local.template_vars)
}

# 2. Standardized VyOS CLI commands generated from the same NetBox data
resource "local_file" "vyos_config" {
  filename = "${path.module}/generated/fw-edge-01-vyos.cfg"
  content  = templatefile("${path.module}/templates/vyos.tftpl", local.template_vars)
}

# 3. Standardized FortiGate CLI config generated from the same NetBox data
resource "local_file" "fortigate_config" {
  filename = "${path.module}/generated/fw-edge-01-fortigate.conf"
  content  = templatefile("${path.module}/templates/fortigate.tftpl", local.template_vars)
}

# 4. Inspect live firewall state during terraform plan to detect manual firewall drift
data "external" "live_fw_state" {
  program = ["bash", "${path.module}/../scripts/check-fw-drift.sh"]
}

# 5. Push and enforce the generated nftables ruleset + interface IPs on the live lab firewall
resource "terraform_data" "apply_firewall" {
  triggers_replace = [
    local_file.nftables_config.content_sha256,
    jsonencode(local.address_objects),
    data.external.live_fw_state.result["firewall_state"]
  ]

  provisioner "local-exec" {
    command = "bash ${path.module}/../scripts/apply-firewall.sh ${local_file.nftables_config.filename}"
  }
}
