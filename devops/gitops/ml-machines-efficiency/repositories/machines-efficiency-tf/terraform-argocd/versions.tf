terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_client_config" "default" {}

# The cluster is READ here, not created. Terraform cannot configure a provider
# from an attribute of a resource created in the same apply - that is the whole
# reason this is a separate root module with its own state.
data "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.zone
  project  = var.project_id
}

locals {
  host = "https://${data.google_container_cluster.primary.endpoint}"
  ca   = base64decode(data.google_container_cluster.primary.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = local.host
    cluster_ca_certificate = local.ca
    token                  = data.google_client_config.default.access_token
  }
}

provider "kubernetes" {
  host                   = local.host
  cluster_ca_certificate = local.ca
  token                  = data.google_client_config.default.access_token
}
