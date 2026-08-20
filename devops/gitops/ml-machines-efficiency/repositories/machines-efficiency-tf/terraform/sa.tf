resource "google_service_account" "github_actions" {
  project      = var.project_id
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  description  = "Builds and pushes Docker images. Has NO access to the cluster."

  depends_on = [time_sleep.wait]
}

# ---------------------------------------------------------------------------
# Deliberately no cluster roles here.
#
# Push model (kubectl set image) needed roles/container.developer and
# roles/container.clusterViewer. container.developer grants full access to
# Kubernetes objects in EVERY cluster in the project.
#
# Pull model: CI builds an image, pushes it to Artifact Registry and commits the
# new tag to the config repository. ArgoCD, running inside the cluster, pulls
# from Git. CI therefore needs exactly one permission, granted on the repository
# itself in iam.tf -> artifactregistry.writer.
#
# Removing cluster access is what makes master_authorized_cidrs usable.
# ---------------------------------------------------------------------------
