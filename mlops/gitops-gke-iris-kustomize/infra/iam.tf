# ---------- account for GitHub Actions ----------

resource "google_service_account" "ci" {
  account_id   = "${var.name}-gh-ci"
  display_name = "GitHub Actions CI"
}

resource "google_artifact_registry_repository_iam_member" "ci_push" {
  location   = google_artifact_registry_repository.docker.location
  repository = google_artifact_registry_repository.docker.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.ci.email}"
}

# ---------- Workload Identity Federation ----------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool-2"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.this]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository_owner == '${var.github_owner}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.app_repo}"
}

# ---------- account for API pods ----------

resource "google_service_account" "api" {
  account_id   = "${var.name}-api"
  display_name = "Iris API pods"
}

resource "google_storage_bucket_iam_member" "api_read" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_service_account_iam_member" "api_wi" {
  for_each = var.enable_gke ? toset(var.namespaces) : toset([])

  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${each.value}/iris-api]"

  depends_on = [google_container_cluster.this]
}

# ---------- account for the training job ----------

resource "google_service_account" "trainer" {
  account_id   = "${var.name}-trainer"
  display_name = "Iris training job"
}

resource "google_storage_bucket_iam_member" "trainer_write" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.trainer.email}"
}

resource "google_service_account_iam_member" "trainer_wi" {
  count = var.enable_gke ? 1 : 0

  service_account_id = google_service_account.trainer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[iris-training/iris-trainer]"

  depends_on = [google_container_cluster.this]
}


resource "time_sleep" "wait_for_wi_pool" {
  count = var.enable_gke ? 1 : 0

  depends_on      = [google_container_cluster.this]
  create_duration = "60s"
}
