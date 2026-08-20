variable "project_name" {
  type    = string
  default = "ml-gke-iris"
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "zone" {
  type    = string
  default = "europe-west1-b"
}

variable "zone2" {
  type    = string
  default = "europe-west1-c"
}

variable "arr_repository_name" {
  type    = string
  default = "ml-ops-iris"
}

variable "cluster_name" {
  type    = string
  default = "ml-ops-iris"
}

variable "github_repository" {
  description = "GitHub repository: 'owner/repo'"
  type        = string
  default     = "dariusz-trawicki/mlops_gke_iris"
}
