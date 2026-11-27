output "resource_group" {
  value = azurerm_resource_group.rg.name
}

output "firewall_mgmt_url" {
  value = "https://${azurerm_public_ip.fw_mgmt.ip_address}"
}

output "firewall_mgmt_ssh" {
  value = "ssh ${var.admin_username}@${azurerm_public_ip.fw_mgmt.ip_address}"
}

output "ilb_frontend" {
  value = local.ilb_ip
}

output "snat_mode" {
  value = var.snat_mode
}

output "steer_through_firewall" {
  value = var.steer_through_firewall
}

output "test_vms" {
  value = { for k, v in azurerm_linux_virtual_machine.vm : k => { name = v.name, ip = local.spokes[k].vm_ip, nic = azurerm_network_interface.vm[k].name } }
}

output "targets" {
  description = "FQDN, private endpoint IP and the spoke that hosts it."
  value = merge(
    { for k, st in azurerm_storage_account.st : "blob-${k}" => {
      fqdn  = "${st.name}.blob.core.windows.net"
      ip    = azurerm_private_endpoint.blob[k].private_service_connection[0].private_ip_address
      spoke = k
    } },
    { "vault-spoke1" = {
      fqdn  = "${azurerm_key_vault.kv.name}.vault.azure.net"
      ip    = azurerm_private_endpoint.vault.private_service_connection[0].private_ip_address
      spoke = "spoke1"
    } }
  )
}
