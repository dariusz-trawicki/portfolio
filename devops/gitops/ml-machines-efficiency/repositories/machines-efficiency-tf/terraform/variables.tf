variable "project_id" {
  description = "Existing GCP project. Terraform does NOT create it - billing must already be enabled."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-central2" # Warsaw
}

variable "zone" {
  type    = string
  default = "europe-central2-a"
}

variable "zone2" {
  description = "Second zone for a multi-zonal cluster. Set to null for single-zone (halves the node bill)."
  type        = string
  default     = "europe-central2-b"
}

variable "cluster_name" {
  type    = string
  default = "mlops-tests-gke"
}

variable "arr_repository_name" {
  type    = string
  default = "mlops-apps"
}

variable "github_repository" {
  description = "Application repo holding code + CI workflow: 'owner/repo'"
  type        = string
}

variable "general_machine_type" {
  description = <<-EOT
    e2-small (2 GB) leaves ~1.4 GB allocatable after system pods - not enough
    once ArgoCD is in the cluster. e2-medium is the practical minimum.
  EOT
  type        = string
  default     = "e2-medium"
}

variable "general_node_count" {
  description = "Nodes PER ZONE. With zone2 set, the real total is this number x 2."
  type        = number
  default     = 1
}

variable "spot_machine_type" {
  type    = string
  default = "e2-small"
}

variable "master_authorized_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach the public control-plane endpoint.
    Safe to set only because CI no longer touches the cluster - GitHub-hosted
    runners have dynamic IPs and could never be allow-listed.
    Leave empty to keep the endpoint reachable from anywhere (auth still applies).
  EOT
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}
