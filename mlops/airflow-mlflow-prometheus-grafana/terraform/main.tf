terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────────
# GCS BUCKET — raw data
# ─────────────────────────────────────────────
resource "google_storage_bucket" "raw_data" {
  name          = "${var.project_id}-titanic-raw"
  location      = var.region
  force_destroy = true # for development: allows bucket deletion even if it contains objects (use with caution in production!)

  # File versioning (useful in MLOps)
  versioning {
    enabled = true
  }

  # Lifecycle: old versions deleted after 30 days
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      age                = 30
    }
    action {
      type = "Delete"
    }
  }

  # Block public access
  public_access_prevention = "enforced"

  uniform_bucket_level_access = true

  labels = {
    env     = var.environment
    project = "titanic-mlops"
    managed = "terraform"
  }
}

# ─────────────────────────────────────────────
# SERVICE ACCOUNT — for Airflow DAG
# ─────────────────────────────────────────────
resource "google_service_account" "airflow_sa" {
  account_id   = "airflow-titanic-sa"
  display_name = "Airflow SA — Titanic MLOps"
  description  = "SA used by Airflow to read raw data from GCS"
}

# ─────────────────────────────────────────────
# IAM — assign SA role to bucket
# ─────────────────────────────────────────────

# Read access (Airflow downloads CSV)
resource "google_storage_bucket_iam_member" "airflow_reader" {
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.airflow_sa.email}"
}

# Optional: write access (if Airflow also needs to upload data)
resource "google_storage_bucket_iam_member" "airflow_writer" {
  count  = var.allow_airflow_write ? 1 : 0
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.airflow_sa.email}"
}

# ─────────────────────────────────────────────
# SA KEY — for local use / Kubernetes secret
# ─────────────────────────────────────────────
resource "google_service_account_key" "airflow_sa_key" {
  service_account_id = google_service_account.airflow_sa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

# Save key to local file
resource "local_file" "sa_key_json" {
  content  = base64decode(google_service_account_key.airflow_sa_key.private_key)
  filename = "${path.module}/keys/gcp-key.json"

  # Owner-only permissions
  file_permission = "0600"
}
