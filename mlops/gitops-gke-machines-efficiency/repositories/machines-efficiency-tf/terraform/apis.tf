# Replaces the project-factory module: the project already exists, only the
# APIs need enabling.
locals {
  required_apis = [
    "compute.googleapis.com",
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.required_apis)

  project = var.project_id
  service = each.value

  # Disabling APIs on destroy can break unrelated resources in a shared
  # project and slows down repeated apply/destroy cycles.
  disable_on_destroy = false
}
