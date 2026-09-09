variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type    = string
  default = "europe-central2"
}

variable "zone" {
  type    = string
  default = "europe-central2-a"
}

variable "name" {
  type        = string
  default     = "iris"
  description = "Prefix for resource names"
}

variable "github_owner" {
  type        = string
  description = "Owner of the repositories on GitHub"
}

variable "app_repo" {
  type    = string
  default = "iris-mlops-app"
}

variable "namespaces" {
  type        = list(string)
  default     = ["iris-dev", "iris-prod"]
  description = "Application namespaces — used for Workload Identity bindings"
}

variable "node_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "use_spot_nodes" {
  type    = bool
  default = true
}

variable "enable_gke" {
  type        = bool
  default     = false
  description = "Creates the cluster and node pool."
}
