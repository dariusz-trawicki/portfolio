## IAM - WORKLOAD IDENTITY
resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository}"
}

## IAM - ARTIFACT REGISTRY
resource "google_artifact_registry_repository_iam_member" "github_writer" {
  project    = module.project.project_id
  location   = google_artifact_registry_repository.docker_repo.location
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_artifact_registry_repository_iam_member" "gke_reader" {
  project    = module.project.project_id
  location   = google_artifact_registry_repository.docker_repo.location
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.reader"

  member = "serviceAccount:${google_service_account.kubernetes.email}"

  depends_on = [
    google_service_account.kubernetes,
    google_artifact_registry_repository.docker_repo
  ]
}

resource "google_project_iam_member" "kubernetes_logging" {
  project = module.project.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.kubernetes.email}"
}

resource "google_project_iam_member" "kubernetes_monitoring" {
  project = module.project.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.kubernetes.email}"
}

resource "google_project_iam_member" "kubernetes_monitoring_viewer" {
  project = module.project.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.kubernetes.email}"
}