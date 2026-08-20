output "endpoint" {
  value = azurerm_cognitive_account.document_intelligence.endpoint
}

output "key" {
  value     = azurerm_cognitive_account.document_intelligence.primary_access_key
  sensitive = true
}

# Ready-to-paste .env fragment.
#
# Terraform writes the access key into the state file in plain text, which is
# why terraform.tfstate is gitignored here. A production setup would keep state
# in a remote backend with encryption and state locking - an Azure Storage
# container rather than a local file.
output "env_file" {
  value     = <<-EOT
    AZURE_DI_ENDPOINT=${azurerm_cognitive_account.document_intelligence.endpoint}
    AZURE_DI_KEY=${azurerm_cognitive_account.document_intelligence.primary_access_key}
  EOT
  sensitive = true
}
