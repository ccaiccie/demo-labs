# Private endpoints that live in spoke VNets, forced through a Palo Alto VM-Series in the hub.
#
#   hub   10.0.0.0/16   mgmt 10.0.0.0/24 | untrust 10.0.1.0/24 | trust 10.0.2.0/24 (FW 10.0.2.4, ILB 10.0.2.100)
#   spoke1 10.1.0.0/16  app 10.1.1.0/24 (vm1 10.1.1.4) | pe 10.1.2.0/24 (blob + vault)
#   spoke2 10.2.0.0/16  app 10.2.1.0/24 (vm2 10.2.1.4) | pe 10.2.2.0/24 (blob)

locals {
  hub_cidr      = "10.0.0.0/16"
  fw_trust_ip   = "10.0.2.4"
  ilb_ip        = "10.0.2.100"
  fw_mgmt_ip    = "10.0.0.4"
  fw_untrust_ip = "10.0.1.4"

  spokes = {
    spoke1 = { cidr = "10.1.0.0/16", app = "10.1.1.0/24", pe = "10.1.2.0/24", vm_ip = "10.1.1.4" }
    spoke2 = { cidr = "10.2.0.0/16", app = "10.2.1.0/24", pe = "10.2.2.0/24", vm_ip = "10.2.1.4" }
  }

  app_subnets = [for s in local.spokes : s.app]

  # Sources the private endpoint NSG should allow. With firewall SNAT the endpoint only ever sees the
  # firewall's trust IP. With disableSnatOnPL it sees the original client IP, so the app subnets are allowed.
  pe_allowed_sources = var.snat_mode == "firewall_snat" ? ["${local.fw_trust_ip}/32"] : local.app_subnets

  tags = { lab = "pe-in-spokes-through-palo-alto", managed_by = "terraform" }
}

resource "random_string" "sfx" {
  length  = 5
  upper   = false
  special = false
}

data "azurerm_client_config" "me" {}

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.prefix}"
  location = var.location
  tags     = local.tags
}

# ------------------------------------------------------------------ hub
resource "azurerm_virtual_network" "hub" {
  name                = "vnet-${var.prefix}-hub"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = [local.hub_cidr]
  tags                = local.tags
}

resource "azurerm_subnet" "mgmt" {
  name                 = "snet-mgmt"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = ["10.0.0.0/24"]
}

resource "azurerm_subnet" "untrust" {
  name                 = "snet-untrust"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_subnet" "trust" {
  name                 = "snet-trust"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = ["10.0.2.0/24"]
}

resource "azurerm_network_security_group" "mgmt" {
  name                = "nsg-${var.prefix}-fw-mgmt"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  security_rule {
    name                       = "allow-admin"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = var.mgmt_allowed_cidr
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_ranges    = ["22", "443"]
  }
}

resource "azurerm_network_security_group" "dataplane" {
  name                = "nsg-${var.prefix}-fw-dataplane"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  # The firewall is the policy point; let everything private reach it.
  security_rule {
    name                       = "allow-private"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_address_prefix      = "VirtualNetwork"
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_range     = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "mgmt" {
  subnet_id                 = azurerm_subnet.mgmt.id
  network_security_group_id = azurerm_network_security_group.mgmt.id
}

resource "azurerm_subnet_network_security_group_association" "untrust" {
  subnet_id                 = azurerm_subnet.untrust.id
  network_security_group_id = azurerm_network_security_group.dataplane.id
}

resource "azurerm_subnet_network_security_group_association" "trust" {
  subnet_id                 = azurerm_subnet.trust.id
  network_security_group_id = azurerm_network_security_group.dataplane.id
}

# ------------------------------------------------------------------ VM-Series
resource "azurerm_public_ip" "fw_mgmt" {
  name                = "pip-${var.prefix}-fw-mgmt"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_public_ip" "fw_untrust" {
  name                = "pip-${var.prefix}-fw-untrust"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_interface" "fw_mgmt" {
  name                = "nic-${var.prefix}-fw-mgmt"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.mgmt.id
    private_ip_address_allocation = "Static"
    private_ip_address            = local.fw_mgmt_ip
    public_ip_address_id          = azurerm_public_ip.fw_mgmt.id
  }
}

resource "azurerm_network_interface" "fw_untrust" {
  name                  = "nic-${var.prefix}-fw-untrust"
  location              = azurerm_resource_group.rg.location
  resource_group_name   = azurerm_resource_group.rg.name
  ip_forwarding_enabled = true
  tags                  = local.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.untrust.id
    private_ip_address_allocation = "Static"
    private_ip_address            = local.fw_untrust_ip
    public_ip_address_id          = azurerm_public_ip.fw_untrust.id
  }
}

resource "azurerm_network_interface" "fw_trust" {
  name                  = "nic-${var.prefix}-fw-trust"
  location              = azurerm_resource_group.rg.location
  resource_group_name   = azurerm_resource_group.rg.name
  ip_forwarding_enabled = true
  # The opt-in tag that keeps private endpoint return traffic symmetric without SNAT (case-sensitive).
  tags = merge(local.tags, var.snat_mode == "disable_snat_on_pl" ? { disableSnatOnPL = "true" } : {})

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.trust.id
    private_ip_address_allocation = "Static"
    private_ip_address            = local.fw_trust_ip
  }
}

resource "azurerm_linux_virtual_machine" "fw" {
  name                            = "vm-${var.prefix}-fw1"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  size                            = var.fw_vm_size
  admin_username                  = var.admin_username
  admin_password                  = var.fw_admin_password
  disable_password_authentication = false
  # First NIC is management on VM-Series (eth0 = mgmt, then ethernet1/1 untrust, ethernet1/2 trust).
  network_interface_ids = [
    azurerm_network_interface.fw_mgmt.id,
    azurerm_network_interface.fw_untrust.id,
    azurerm_network_interface.fw_trust.id,
  ]
  tags = local.tags

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "paloaltonetworks"
    offer     = "vmseries-flex"
    sku       = var.fw_sku
    version   = var.fw_version
  }

  plan {
    publisher = "paloaltonetworks"
    product   = "vmseries-flex"
    name      = var.fw_sku
  }

  boot_diagnostics {}
}

# ------------------------------------------------------------------ internal load balancer (HA ports)
resource "azurerm_lb" "ilb" {
  name                = "lbi-${var.prefix}-fw"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"
  tags                = local.tags

  frontend_ip_configuration {
    name                          = "fe-trust"
    subnet_id                     = azurerm_subnet.trust.id
    private_ip_address_allocation = "Static"
    private_ip_address            = local.ilb_ip
  }
}

resource "azurerm_lb_backend_address_pool" "trust" {
  name            = "be-fw-trust"
  loadbalancer_id = azurerm_lb.ilb.id
}

resource "azurerm_network_interface_backend_address_pool_association" "fw_trust" {
  network_interface_id    = azurerm_network_interface.fw_trust.id
  ip_configuration_name   = "ipconfig1"
  backend_address_pool_id = azurerm_lb_backend_address_pool.trust.id
}

# PAN-OS answers this probe because ethernet1/2 has a management profile allowing HTTPS from 168.63.129.16.
resource "azurerm_lb_probe" "https" {
  name                = "probe-https"
  loadbalancer_id     = azurerm_lb.ilb.id
  protocol            = "Tcp"
  port                = 443
  interval_in_seconds = 5
}

resource "azurerm_lb_rule" "ha_ports" {
  name                           = "ha-ports"
  loadbalancer_id                = azurerm_lb.ilb.id
  protocol                       = "All"
  frontend_port                  = 0
  backend_port                   = 0
  frontend_ip_configuration_name = "fe-trust"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.trust.id]
  probe_id                       = azurerm_lb_probe.https.id
  load_distribution              = "SourceIPProtocol"
}

# ------------------------------------------------------------------ spokes
resource "azurerm_virtual_network" "spoke" {
  for_each            = local.spokes
  name                = "vnet-${var.prefix}-${each.key}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = [each.value.cidr]
  tags                = local.tags
}

resource "azurerm_subnet" "app" {
  for_each             = local.spokes
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.spoke[each.key].name
  address_prefixes     = [each.value.app]
}

resource "azurerm_subnet" "pe" {
  for_each             = local.spokes
  name                 = "snet-pe"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.spoke[each.key].name
  address_prefixes     = [each.value.pe]
  # The switch that lets a UDR (and an NSG) apply to private endpoints in this subnet.
  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_virtual_network_peering" "hub_to_spoke" {
  for_each                     = local.spokes
  name                         = "hub-to-${each.key}"
  resource_group_name          = azurerm_resource_group.rg.name
  virtual_network_name         = azurerm_virtual_network.hub.name
  remote_virtual_network_id    = azurerm_virtual_network.spoke[each.key].id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
}

resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  for_each                     = local.spokes
  name                         = "${each.key}-to-hub"
  resource_group_name          = azurerm_resource_group.rg.name
  virtual_network_name         = azurerm_virtual_network.spoke[each.key].name
  remote_virtual_network_id    = azurerm_virtual_network.hub.id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
}

# ------------------------------------------------------------------ routing: the part that forces the firewall
# App subnet route table, per spoke:
#   * other spokes' address spaces -> ILB  (classic hub-and-spoke, spokes are not peered to each other)
#   * this spoke's own PE subnet   -> ILB  (the same-spoke case; needs network policies on snet-pe and a
#                                          prefix at least as long as the VNet's, so /24 works, /8 or 0/0 never will)
resource "azurerm_route_table" "app" {
  for_each                      = local.spokes
  name                          = "rt-${var.prefix}-${each.key}-app"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  bgp_route_propagation_enabled = false
  tags                          = local.tags
}

resource "azurerm_route" "to_other_spokes" {
  for_each = {
    for pair in flatten([
      for src, s in local.spokes : [
        for dst, d in local.spokes : { key = "${src}-${dst}", src = src, cidr = d.cidr, dst = dst } if src != dst
      ]
    ]) : pair.key => pair
  }
  name                   = "to-${each.value.dst}"
  resource_group_name    = azurerm_resource_group.rg.name
  route_table_name       = azurerm_route_table.app[each.value.src].name
  address_prefix         = each.value.cidr
  next_hop_type          = "VirtualAppliance"
  next_hop_in_ip_address = local.ilb_ip
}

resource "azurerm_route" "to_own_pe_subnet" {
  for_each               = var.steer_through_firewall ? local.spokes : {}
  name                   = "own-pe-subnet-via-fw"
  resource_group_name    = azurerm_resource_group.rg.name
  route_table_name       = azurerm_route_table.app[each.key].name
  address_prefix         = each.value.pe
  next_hop_type          = "VirtualAppliance"
  next_hop_in_ip_address = local.ilb_ip
}

resource "azurerm_subnet_route_table_association" "app" {
  for_each       = local.spokes
  subnet_id      = azurerm_subnet.app[each.key].id
  route_table_id = azurerm_route_table.app[each.key].id
}

# ------------------------------------------------------------------ NSG on the private endpoint subnets
resource "azurerm_network_security_group" "pe" {
  for_each            = var.lock_pe_subnets_with_nsg ? local.spokes : {}
  name                = "nsg-${var.prefix}-${each.key}-pe"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  security_rule {
    name                       = "allow-https-from-firewall-path"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefixes    = local.pe_allowed_sources
    source_port_range          = "*"
    destination_address_prefix = each.value.pe
    destination_port_range     = "443"
  }

  security_rule {
    name                       = "deny-other-vnet"
    priority                   = 4000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_address_prefix      = "VirtualNetwork"
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_range     = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "pe" {
  for_each                  = var.lock_pe_subnets_with_nsg ? local.spokes : {}
  subnet_id                 = azurerm_subnet.pe[each.key].id
  network_security_group_id = azurerm_network_security_group.pe[each.key].id
}

# ------------------------------------------------------------------ test clients
resource "azurerm_network_interface" "vm" {
  for_each            = local.spokes
  name                = "nic-${var.prefix}-${each.key}-vm"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.app[each.key].id
    private_ip_address_allocation = "Static"
    private_ip_address            = each.value.vm_ip
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  for_each              = local.spokes
  name                  = "vm-${var.prefix}-${each.key}"
  location              = azurerm_resource_group.rg.location
  resource_group_name   = azurerm_resource_group.rg.name
  size                  = var.test_vm_size
  admin_username        = var.admin_username
  network_interface_ids = [azurerm_network_interface.vm[each.key].id]
  tags                  = local.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  boot_diagnostics {}
}

# ------------------------------------------------------------------ PaaS: storage in both spokes, a vault in spoke1
resource "azurerm_storage_account" "st" {
  for_each                        = local.spokes
  name                            = substr("st${var.prefix}${each.key}${random_string.sfx.result}", 0, 24)
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_key_vault" "kv" {
  name                          = substr("kv-${var.prefix}-${random_string.sfx.result}", 0, 24)
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  tenant_id                     = data.azurerm_client_config.me.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  public_network_access_enabled = false
  purge_protection_enabled      = false
  soft_delete_retention_days    = 7
  tags                          = local.tags
}

# ------------------------------------------------------------------ private DNS (zones linked to every VNet; no resolver needed for this lab)
resource "azurerm_private_dns_zone" "z" {
  for_each            = toset(["privatelink.blob.core.windows.net", "privatelink.vaultcore.azure.net"])
  name                = each.key
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags
}

locals {
  vnet_ids = merge({ hub = azurerm_virtual_network.hub.id }, { for k, v in azurerm_virtual_network.spoke : k => v.id })
  zone_links = {
    for pair in setproduct(keys(azurerm_private_dns_zone.z), keys(local.vnet_ids)) : "${pair[0]}|${pair[1]}" => { zone = pair[0], vnet = pair[1] }
  }
}

resource "azurerm_private_dns_zone_virtual_network_link" "l" {
  for_each              = local.zone_links
  name                  = "link-${each.value.vnet}"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.z[each.value.zone].name
  virtual_network_id    = local.vnet_ids[each.value.vnet]
  registration_enabled  = false
}

resource "azurerm_private_endpoint" "blob" {
  for_each            = local.spokes
  name                = "pe-${var.prefix}-${each.key}-blob"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.pe[each.key].id
  tags                = local.tags

  private_service_connection {
    name                           = "blob"
    private_connection_resource_id = azurerm_storage_account.st[each.key].id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.z["privatelink.blob.core.windows.net"].id]
  }
}

resource "azurerm_private_endpoint" "vault" {
  name                = "pe-${var.prefix}-spoke1-vault"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.pe["spoke1"].id
  tags                = local.tags

  private_service_connection {
    name                           = "vault"
    private_connection_resource_id = azurerm_key_vault.kv.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.z["privatelink.vaultcore.azure.net"].id]
  }
}
