# tworzy tzw. "grupę zasobów" (kontener na zasoby w Azure)
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# tworzy zasób Azure OpenAI
resource "azurerm_cognitive_account" "openai" {
  name                = var.cognitive_account_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_cognitive_deployment" "gpt" {
  name                 = var.deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }

  sku {
    name     = "Standard"
    capacity = var.capacity
  }
}
