variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  type = string
}

variable "bucket_name" {
  description = "Bucket for data"
  type        = string
}

variable "dataset_name" {
  type        = string
  description = "Name of the BigQuery dataset"
}
