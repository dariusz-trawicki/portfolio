terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}

  # Pinned explicitly rather than inheriting whatever the CLI's current default
  # happens to be. With more than one subscription available, relying on the
  # ambient default is how resources end up created in the wrong place.
  subscription_id = var.subscription_id
}

# Cognitive Services account names must be globally unique.
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "ocr" {
  name     = "rg-ocr-demo"
  location = var.location
}

resource "azurerm_cognitive_account" "document_intelligence" {
  name                = "di-ocr-demo-${random_string.suffix.result}"
  location            = azurerm_resource_group.ocr.location
  resource_group_name = azurerm_resource_group.ocr.name

  # NOTE: Azure still uses the legacy kind "FormRecognizer" even though the
  # product is now called Document Intelligence. "DocumentIntelligence" is not
  # a valid value and fails with an unknown-kind error.
  kind     = "FormRecognizer"
  sku_name = var.sku

  # Required if you ever want to authenticate with an Entra ID token instead of
  # an access key. Adding it later forces the resource to be recreated, so it is
  # cheaper to set up front.
  custom_subdomain_name = "di-ocr-demo-${random_string.suffix.result}"

  # A key is required regardless, but in a regulated environment it is worth
  # stating network exposure explicitly rather than inheriting the default.
  public_network_access_enabled = true

  tags = {
    project     = "ocr-evidence-demo"
    environment = "demo"
    managed_by  = "terraform"
  }
}
