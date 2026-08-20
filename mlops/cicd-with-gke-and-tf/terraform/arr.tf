resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.arr_repository_name
  project       = module.project.project_id
  description   = "Artifact Registry for Iris Flower Classification project"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = 5
    }
  }

  cleanup_policies {
    id     = "delete-untagged-old"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [
    module.project
  ]
}