output "route_server_id" {
  description = "Resource ID of Azure Route Server rs1."
  value       = azurerm_route_server.rs1.id
}

output "route_server_virtual_router_ips" {
  description = "Primary and secondary BGP peering IPs of Route Server rs1."
  value       = azurerm_route_server.rs1.virtual_router_ips
}

output "route_server_asn" {
  description = "BGP ASN of Azure Route Server (65515)."
  value       = azurerm_route_server.rs1.virtual_router_asn
}

output "nva_private_ips" {
  description = "Private IP addresses of nva100-1 and nva100-2."
  value       = { for k, v in azurerm_network_interface.nva : "nva100-${k}" => v.private_ip_address }
}

output "vpn_gateway_name" {
  description = "Active-active VPN Gateway name."
  value       = azurerm_virtual_network_gateway.vpn_gw.name
}
