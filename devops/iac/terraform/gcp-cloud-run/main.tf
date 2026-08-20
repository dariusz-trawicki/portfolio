module "cloud_run_service" {
  source  = "GoogleCloudPlatform/cloud-run/google"
  version = "~> 0.10.0"

  service_name = "default"
  project_id   = module.project.project_id
  location     = var.region
  image        = "gcr.io/cloudrun/hello"

  service_annotations = {
    "run.googleapis.com/ingress" = "all"
  }

  timeout_seconds = 3600
}


data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location    = var.region
  project     = module.project.project_id
  service     = module.cloud_run_service.service_name
  policy_data = data.google_iam_policy.noauth.policy_data
}
