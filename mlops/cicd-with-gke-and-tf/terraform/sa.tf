resource "google_service_account" "github_actions" {
  project      = module.project.project_id
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  description  = "Service Account used by GitHub Actions to push Docker images"

  depends_on = [
    module.project
  ]
}

resource "google_project_iam_member" "github_actions_gke_cluster_viewer" {
  project = module.project.project_id
  role    = "roles/container.clusterViewer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "github_actions_gke_developer" {
  project = module.project.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}
