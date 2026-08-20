output "project_id" {
  value = var.project_id
}

output "github_actions_sa_email" {
  description = "Put in the GCP_SERVICE_ACCOUNT GitHub secret"
  value       = google_service_account.github_actions.email
}

output "github_wif_provider" {
  description = "Put in the GCP_WORKLOAD_IDENTITY_PROVIDER GitHub secret"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "artifact_registry_url" {
  description = "Docker image prefix"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "cluster_name" {
  value = google_container_cluster.primary.name
}

output "cluster_location" {
  value = google_container_cluster.primary.location
}

output "get_credentials_command" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --zone ${google_container_cluster.primary.location} --project ${var.project_id}"
}

output "nat_ip" {
  description = "Stable outbound IP of the cluster"
  value       = google_compute_address.nat.address
}
