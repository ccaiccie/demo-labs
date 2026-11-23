# -----------------------------------------------------------------------------
# 1. Site
# -----------------------------------------------------------------------------
resource "netbox_site" "branch_dc" {
  name        = var.site_name
  slug        = var.site_slug
  status      = "active"
  description = "Standardized branch datacenter managed by Terraform"
}

# -----------------------------------------------------------------------------
# 2. VLANs and IPv4 Prefixes
# -----------------------------------------------------------------------------
resource "netbox_vlan" "vlans" {
  for_each = var.vlans

  name        = each.value.name
  vid         = each.value.vid
  site_id     = netbox_site.branch_dc.id
  status      = "active"
  description = each.value.description
}

resource "netbox_prefix" "prefixes" {
  for_each = var.vlans

  prefix      = each.value.prefix
  status      = "active"
  site_id     = netbox_site.branch_dc.id
  vlan_id     = netbox_vlan.vlans[each.key].id
  description = "${each.value.zone} zone - ${each.value.description}"
}

# -----------------------------------------------------------------------------
# 3. Hardware Catalog (Manufacturers, Device Types, Device Roles)
# -----------------------------------------------------------------------------
resource "netbox_manufacturer" "vyos" {
  name = "VyOS"
}

resource "netbox_manufacturer" "arista" {
  name = "Arista"
}

resource "netbox_device_type" "edge_fw" {
  model           = "Edge-FW-1000"
  manufacturer_id = netbox_manufacturer.vyos.id
  u_height        = 1
}

resource "netbox_device_type" "core_sw" {
  model           = "Core-SW-48"
  manufacturer_id = netbox_manufacturer.arista.id
  u_height        = 1
}

resource "netbox_device_role" "firewall" {
  name      = "Edge Firewall"
  color_hex = "d9534f"
}

resource "netbox_device_role" "core_switch" {
  name      = "Core Switch"
  color_hex = "2b7de9"
}

# -----------------------------------------------------------------------------
# 4. Devices
# -----------------------------------------------------------------------------
resource "netbox_device" "fw_edge_01" {
  name           = "fw-edge-01"
  device_type_id = netbox_device_type.edge_fw.id
  role_id        = netbox_device_role.firewall.id
  site_id        = netbox_site.branch_dc.id
  status         = "active"
  comments       = "Primary branch perimeter firewall (managed by Terraform)"
}

resource "netbox_device" "sw_core_01" {
  name           = "sw-core-01"
  device_type_id = netbox_device_type.core_sw.id
  role_id        = netbox_device_role.core_switch.id
  site_id        = netbox_site.branch_dc.id
  status         = "active"
  comments       = "Core distribution switch (managed by Terraform)"
}

# -----------------------------------------------------------------------------
# 5. Interfaces & IP Addresses
# -----------------------------------------------------------------------------
resource "netbox_device_interface" "fw_wan" {
  name        = "eth-wan"
  device_id   = netbox_device.fw_edge_01.id
  type        = "1000base-t"
  description = "WAN uplink to ISP transit"
}

resource "netbox_device_interface" "fw_zones" {
  for_each = var.vlans

  name            = each.value.iface_name
  device_id       = netbox_device.fw_edge_01.id
  type            = "1000base-t"
  mode            = "access"
  untagged_vlan_id = netbox_vlan.vlans[each.key].id
  description     = "${each.value.zone} gateway (${each.value.name} / VLAN ${each.value.vid})"
}

resource "netbox_device_interface" "sw_mgmt" {
  name          = "eth1"
  device_id     = netbox_device.sw_core_01.id
  type          = "1000base-t"
  mode          = "access"
  untagged_vlan_id = netbox_vlan.vlans["mgmt_oob"].id
  description   = "Management uplink to fw-edge-01"
}

resource "netbox_ip_address" "fw_zone_ips" {
  for_each = var.vlans

  ip_address          = each.value.gateway_ip
  status              = "active"
  device_interface_id = netbox_device_interface.fw_zones[each.key].id
  description         = "${each.value.zone} gateway IP for ${each.value.name}"
}

resource "netbox_ip_address" "sw_mgmt_ip" {
  ip_address          = "192.0.2.10/24"
  status              = "active"
  device_interface_id = netbox_device_interface.sw_mgmt.id
  description         = "Management IP for sw-core-01"
}
