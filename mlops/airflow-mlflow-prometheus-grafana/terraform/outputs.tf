output "bucket_url" {
  description = "Bucket URL"
  value       = "gs://${google_storage_bucket.raw_data.name}"
}

output "sa_key_path" {
  description = "Local path to SA key (JSON)"
  value       = local_file.sa_key_json.filename
  sensitive   = true
}
