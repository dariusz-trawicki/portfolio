output "workspace_name" {
  value = azurerm_machine_learning_workspace.ml.name
}

output "resource_group" {
  value = azurerm_resource_group.ml.name
}

output "storage_account" {
  value = azurerm_storage_account.ml.name
}

output "workspace_id" {
  value = azurerm_machine_learning_workspace.ml.id
}
