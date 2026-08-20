# outputs.tf
output "endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "primary_key" {
  value     = azurerm_cognitive_account.openai.primary_access_key
  sensitive = true
}

output "deployment_name" {
  value = azurerm_cognitive_deployment.gpt.name
}
