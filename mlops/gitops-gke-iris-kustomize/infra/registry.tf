resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = var.name
  format        = "DOCKER"
  description   = "Obrazy aplikacji i trenera"

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s"
    }
  }

  depends_on = [google_project_service.this]
}
