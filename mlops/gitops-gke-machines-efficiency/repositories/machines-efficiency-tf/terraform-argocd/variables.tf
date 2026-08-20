variable "project_id" {
  type    = string
  default = "<your_project_id>"
}

variable "region" {
  type    = string
  default = "europe-central2"
}

variable "zone" {
  description = "Must match the cluster location - a zonal cluster lives in a zone, not a region."
  type        = string
  default     = "europe-central2-a"
}

variable "cluster_name" {
  type    = string
  default = "mlops-tests-gke"
}

variable "argocd_chart_version" {
  description = "Pin it. 'latest' is not reproducible."
  type        = string
  default     = "7.8.2"
}

variable "argocd_apps_chart_version" {
  type    = string
  default = "2.0.2"
}

variable "config_repo_url" {
  description = "HTTPS URL of the repo holding Kubernetes manifests (a SECOND repo, separate from the app code)."
  type        = string
}

variable "config_repo_path" {
  type    = string
  default = "k8s"
}

variable "config_repo_revision" {
  type    = string
  default = "main"
}

variable "app_name" {
  type    = string
  default = "manufacturing-efficiency"
}

variable "app_namespace" {
  type    = string
  default = "mlops"
}

variable "config_repo_ssh_key_path" {
  description = "Path to the deploy key private key "
  type        = string
  default     = "~/.ssh/argocd_config_repo"
}
