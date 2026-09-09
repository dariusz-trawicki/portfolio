output "project_id" {
  value = var.project_id
}

output "cluster_name" {
  value = one(google_container_cluster.this[*].name)
}

output "cluster_location" {
  value = one(google_container_cluster.this[*].location)
}

output "registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "models_bucket" {
  value = google_storage_bucket.models.name
}

output "wif_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Value for workflow_identity_provider in GitHub Actions"
}

output "ci_service_account" {
  value = google_service_account.ci.email
}

output "api_service_account" {
  value = google_service_account.api.email
}

output "trainer_service_account" {
  value = google_service_account.trainer.email
}
