terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

resource "azurerm_resource_group" "ml" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "ml" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.ml.name
  location                 = azurerm_resource_group.ml.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_application_insights" "ml" {
  name                = "${var.prefix}-appinsights-6"
  resource_group_name = azurerm_resource_group.ml.name
  location            = azurerm_resource_group.ml.location
  application_type    = "web"

  lifecycle {
    ignore_changes = [workspace_id]
  }
}

resource "azurerm_key_vault" "ml" {
  name                = "${var.prefix}-kv"
  resource_group_name = azurerm_resource_group.ml.name
  location            = azurerm_resource_group.ml.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
}

data "azurerm_client_config" "current" {}

resource "azurerm_machine_learning_workspace" "ml" {
  name                          = "${var.prefix}-workspace-6"
  resource_group_name           = azurerm_resource_group.ml.name
  location                      = azurerm_resource_group.ml.location
  application_insights_id       = azurerm_application_insights.ml.id
  key_vault_id                  = azurerm_key_vault.ml.id
  storage_account_id            = azurerm_storage_account.ml.id
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [container_registry_id, tags]
  }

}

# Blob container to raw MP4 recordings
resource "azurerm_storage_container" "raw_videos" {
  name                  = "raw-videos"
  storage_account_name  = azurerm_storage_account.ml.name
  container_access_type = "private"
}

# Blob container for processed keypoints
resource "azurerm_storage_container" "keypoints" {
  name                  = "keypoints"
  storage_account_name  = azurerm_storage_account.ml.name
  container_access_type = "private"
}


resource "azurerm_machine_learning_compute_cluster" "ml" {
  name                          = "cpu-cluster"
  location                      = azurerm_resource_group.ml.location
  vm_priority                   = "Dedicated"
  vm_size                       = "Standard_DS3_v2"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.ml.id

  scale_settings {
    min_node_count                       = 0
    max_node_count                       = 2
    scale_down_nodes_after_idle_duration = "PT120S"
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_machine_learning_datastore_blobstorage" "keypoints" {
  name                 = "keypoints_store"
  workspace_id         = azurerm_machine_learning_workspace.ml.id
  storage_container_id = azurerm_storage_container.keypoints.resource_manager_id
  account_key          = azurerm_storage_account.ml.primary_access_key
}


resource "azurerm_role_assignment" "workspace_storage" {
  scope                = azurerm_storage_account.ml.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_machine_learning_workspace.ml.identity[0].principal_id
}
