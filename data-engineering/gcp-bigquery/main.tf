# ── 1. Dataset ──────────────────────────────────────────────────────────────
resource "google_bigquery_dataset" "ml_dataset" {
  dataset_id                 = var.dataset_name
  friendly_name              = "ML Training Dataset"
  description                = "Dataset containing training data for ML models"
  location                   = var.region
  delete_contents_on_destroy = true

  labels = {
    env  = "dev"
    team = "mlops"
  }
}

# ── 2. Table with explicit schema ───────────────────────────────────────────
resource "google_bigquery_table" "employees" {
  dataset_id  = google_bigquery_dataset.ml_dataset.dataset_id
  table_id    = "employees"
  description = "Employee data for analysis"

  deletion_protection = false

  schema = jsonencode([
    {
      name        = "id"
      type        = "INTEGER"
      mode        = "REQUIRED"
      description = "Unique employee identifier"
    },
    {
      name = "name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "department"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "salary"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "hire_date"
      type = "DATE"
      mode = "NULLABLE"
    },
    {
      name = "is_active"
      type = "BOOLEAN"
      mode = "NULLABLE"
    }
  ])

  labels = {
    env = "dev"
  }
}

# ── 3. GCS bucket as staging area ───────────────────────────────────────────
resource "google_storage_bucket" "data_bucket" {
  name          = var.bucket_name
  location      = var.region
  force_destroy = true
}

# ── 4. Upload local CSV file to GCS ─────────────────────────────────────────
resource "google_storage_bucket_object" "employees_data" {
  name   = "employees.csv"
  bucket = google_storage_bucket.data_bucket.name
  source = "${path.module}/data/example_data.csv"
}

# ── 5. BigQuery load job: GCS → table ───────────────────────────────────────
resource "google_bigquery_job" "load_employees" {
  job_id   = "load_employees_${formatdate("YYYYMMDDhhmmss", timestamp())}"
  location = var.region

  load {
    source_uris = ["gs://${google_storage_bucket.data_bucket.name}/employees.csv"]

    destination_table {
      project_id = var.project_id
      dataset_id = google_bigquery_dataset.ml_dataset.dataset_id
      table_id   = google_bigquery_table.employees.table_id
    }

    source_format     = "CSV"
    write_disposition = "WRITE_TRUNCATE" # overwrite table on each apply
    skip_leading_rows = 1                # skip CSV header row
    autodetect        = false            # use explicit schema defined above
  }

  depends_on = [
    google_bigquery_dataset.ml_dataset,
    google_bigquery_table.employees,
    google_storage_bucket_object.employees_data,
  ]
}
