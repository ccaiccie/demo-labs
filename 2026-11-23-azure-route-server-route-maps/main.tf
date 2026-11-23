locals {
  tags = {
    lab     = "2026-11-23-azure-route-server-route-maps"
    purpose = "hybrid-path-selection"
  }
}

resource "azurerm_resource_group" "lab" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

# Hub VNet (hub100)
resource "azurerm_virtual_network" "hub100" {
  name                = "hub100"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  address_space       = ["10.100.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "gateway" {
  name                 = "GatewaySubnet"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.hub100.name
  address_prefixes     = ["10.100.0.0/24"]
}

resource "azurerm_subnet" "route_server" {
  name                 = "RouteServerSubnet"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.hub100.name
  address_prefixes     = ["10.100.1.0/24"]
}

resource "azurerm_subnet" "nva" {
  name                 = "NvaSubnet"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.hub100.name
  address_prefixes     = ["10.100.2.0/24"]
}

resource "azurerm_subnet" "workload" {
  name                 = "WorkloadSubnet"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.hub100.name
  address_prefixes     = ["10.100.10.0/24"]
}

# Azure Route Server (rs1) with ASPath Routing Preference and Branch-to-Branch enabled
resource "azurerm_public_ip" "rs1" {
  name                = "pip-rs1"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_route_server" "rs1" {
  name                             = "rs1"
  resource_group_name              = azurerm_resource_group.lab.name
  location                         = azurerm_resource_group.lab.location
  sku                              = "Standard"
  public_ip_address_id             = azurerm_public_ip.rs1.id
  subnet_id                        = azurerm_subnet.route_server.id
  branch_to_branch_traffic_enabled = true
  hub_routing_preference           = "ASPath"
  tags                             = local.tags
}

# Active-Active VPN Gateway (vpn-gw) with BGP ASN 65515
resource "azurerm_public_ip" "vpn_gw_1" {
  name                = "pip-vpn-gw-1"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_public_ip" "vpn_gw_2" {
  name                = "pip-vpn-gw-2"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_virtual_network_gateway" "vpn_gw" {
  name                = "vpn-gw"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  type                = "Vpn"
  vpn_type            = "RouteBased"
  sku                 = "VpnGw1"
  active_active       = true
  bgp_enabled         = true
  tags                = local.tags

  ip_configuration {
    name                          = "vnetGatewayConfig1"
    public_ip_address_id          = azurerm_public_ip.vpn_gw_1.id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.gateway.id
  }

  ip_configuration {
    name                          = "vnetGatewayConfig2"
    public_ip_address_id          = azurerm_public_ip.vpn_gw_2.id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.gateway.id
  }

  bgp_settings {
    asn = 65515
  }
}

# Local Network Gateways for on-prem site20 peers (192.168.20.1 and 192.168.20.2)
resource "azurerm_local_network_gateway" "site20_peer1" {
  name                = "lng-site20-peer1"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  gateway_address     = var.onprem_peer1_public_ip
  address_space       = [var.onprem_prefix]
  tags                = local.tags

  bgp_settings {
    asn                 = var.onprem_asn
    bgp_peering_address = "192.168.20.1"
  }
}

resource "azurerm_local_network_gateway" "site20_peer2" {
  name                = "lng-site20-peer2"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  gateway_address     = var.onprem_peer2_public_ip
  address_space       = [var.onprem_prefix]
  tags                = local.tags

  bgp_settings {
    asn                 = var.onprem_asn
    bgp_peering_address = "192.168.20.2"
  }
}

resource "azurerm_virtual_network_gateway_connection" "site20_peer1" {
  name                       = "conn-vpn-site20-1"
  location                   = azurerm_resource_group.lab.location
  resource_group_name        = azurerm_resource_group.lab.name
  type                       = "IPsec"
  virtual_network_gateway_id = azurerm_virtual_network_gateway.vpn_gw.id
  local_network_gateway_id   = azurerm_local_network_gateway.site20_peer1.id
  bgp_enabled                = true
  shared_key                 = var.vpn_shared_key
  tags                       = local.tags
}

resource "azurerm_virtual_network_gateway_connection" "site20_peer2" {
  name                       = "conn-vpn-site20-2"
  location                   = azurerm_resource_group.lab.location
  resource_group_name        = azurerm_resource_group.lab.name
  type                       = "IPsec"
  virtual_network_gateway_id = azurerm_virtual_network_gateway.vpn_gw.id
  local_network_gateway_id   = azurerm_local_network_gateway.site20_peer2.id
  bgp_enabled                = true
  shared_key                 = var.vpn_shared_key
  tags                       = local.tags
}

# Optional ExpressRoute Gateway (er-gw)
resource "azurerm_public_ip" "er_gw" {
  count               = var.enable_expressroute_gateway ? 1 : 0
  name                = "pip-er-gw"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_virtual_network_gateway" "er_gw" {
  count               = var.enable_expressroute_gateway ? 1 : 0
  name                = "er-gw"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  type                = "ExpressRoute"
  sku                 = "Standard"
  tags                = local.tags

  ip_configuration {
    name                          = "erGatewayConfig"
    public_ip_address_id          = azurerm_public_ip.er_gw[0].id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.gateway.id
  }
}

# Two Linux NVAs (nva100-1 and nva100-2) in ASN 100 peered with Route Server rs1
resource "azurerm_network_interface" "nva" {
  for_each             = { "1" = "10.100.2.4", "2" = "10.100.2.5" }
  name                 = "nic-nva100-${each.key}"
  location             = azurerm_resource_group.lab.location
  resource_group_name  = azurerm_resource_group.lab.name
  ip_forwarding_enabled = true
  tags                 = local.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.nva.id
    private_ip_address_allocation = "Static"
    private_ip_address            = each.value
  }
}

resource "azurerm_linux_virtual_machine" "nva" {
  for_each            = azurerm_network_interface.nva
  name                = "nva100-${each.key}"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  size                = "Standard_B2s"
  admin_username      = var.admin_username
  network_interface_ids = [each.value.id]
  tags                = local.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_route_server_bgp_connection" "nva" {
  for_each        = azurerm_network_interface.nva
  name            = "nva100-${each.key}"
  route_server_id = azurerm_route_server.rs1.id
  peer_asn        = var.nva_asn
  peer_ip         = each.value.private_ip_address
}

# Workload VM for verifying effective routes and path failover
resource "azurerm_network_interface" "workload" {
  name                = "nic-vm-workload"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  tags                = local.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.workload.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "workload" {
  name                  = "vm-workload"
  resource_group_name   = azurerm_resource_group.lab.name
  location              = azurerm_resource_group.lab.location
  size                  = "Standard_B1s"
  admin_username        = var.admin_username
  network_interface_ids = [azurerm_network_interface.workload.id]
  tags                  = local.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
