variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the bucket"
  type        = string
}

variable "environment" {
  description = "Environment: dev / staging / prod"
  type        = string
}

variable "allow_airflow_write" {
  description = "Should Airflow SA have write permissions?"
  type        = bool
}
