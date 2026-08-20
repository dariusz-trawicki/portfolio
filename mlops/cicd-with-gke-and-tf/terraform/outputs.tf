output "project_id" {
  description = "Project ID"
  value       = module.project.project_id
}

output "github_actions_sa_email" {
  value = google_service_account.github_actions.email
}

output "artifact_registry_url" {
  description = "URL to Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${module.project.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "github_wif_provider" {
  description = "Workload Identity Provider resource name for GitHub OIDC"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

# output "github_wif_pool" {
#   description = "Workload Identity Pool resource name"
#   value       = google_iam_workload_identity_pool.github_pool.name
# }

# output "gke_node_service_account_email" {
#   description = "Google Service Account used by GKE node pools (node service account)"
#   value       = google_service_account.kubernetes.email
# }