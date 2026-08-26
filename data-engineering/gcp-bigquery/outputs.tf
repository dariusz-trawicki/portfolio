output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.ml_dataset.dataset_id
}

output "table_id" {
  description = "BigQuery table ID"
  value       = google_bigquery_table.employees.table_id
}

output "table_full_id" {
  description = "Fully qualified BigQuery table ID"
  value       = "${var.project_id}.${google_bigquery_dataset.ml_dataset.dataset_id}.${google_bigquery_table.employees.table_id}"
}

output "staging_bucket" {
  description = "GCS staging bucket name"
  value       = google_storage_bucket.data_bucket.name
}
