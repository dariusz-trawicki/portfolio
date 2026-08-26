# Terraform BigQuery CSV Loader

A minimal Terraform demo that creates a BigQuery dataset, table, and loads data from a local CSV file via GCS.

## Architecture

```
data/example_data.csv
        ↓
google_storage_bucket_object  →  GCS Bucket (staging)
        ↓
google_bigquery_job (LOAD)
        ↓
google_bigquery_table
        ↓
google_bigquery_dataset
```

## Project Structure

```
.
├── main.tf                  # All resources
├── variables.tf             # Input variable declarations
├── outputs.tf               # Output values
├── terraform.tfvars         # Your variable values (not committed)
└── data/
    └── example_data.csv     # Source data file
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.3
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) authenticated (`gcloud auth application-default login`)
- GCP project with the following APIs enabled:
  - `bigquery.googleapis.com`
  - `storage.googleapis.com`

## Usage

### 1. Clone and configure

Create a `terraform.tfvars` file with your appropriate values for:

```hcl
project_id   = "PROJECT_ID"
region       = "REGION"
bucket_name  = "BUCKET_NAME"
dataset_name = "DATASET_NAME"
```


### 2. Replace the data file

Put your own CSV file at `data/example_data.csv`. The header row must match the schema defined in `main.tf`.

Default schema:

| Column       | Type    | Mode     |
|--------------|---------|----------|
| id           | INTEGER | REQUIRED |
| name         | STRING  | REQUIRED |
| department   | STRING  | NULLABLE |
| salary       | FLOAT   | NULLABLE |
| hire_date    | DATE    | NULLABLE |
| is_active    | BOOLEAN | NULLABLE |

### 3. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 4. Verify

```bash
bq query --use_legacy_sql=false \
  'SELECT * FROM `PROJECT_ID.DATASET_NAME.employees` LIMIT 10'
```

## Key Resources

| Resource | Name | Description |
|---|---|---|
| `google_bigquery_dataset` | `ml_training_data` | Dataset container |
| `google_bigquery_table` | `employees` | Table with explicit schema |
| `google_storage_bucket` | `<project>-bq-staging` | Temporary staging bucket |
| `google_storage_bucket_object` | `employees.csv` | Uploaded CSV file |
| `google_bigquery_job` | `load_employees_*` | Load job: GCS → BigQuery |

## Important Notes

- `google_bigquery_job` uses `timestamp()` in `job_id`, which means a new job is created on every `terraform apply`. This is intentional for a demo — in production, use a `null_resource` with `triggers` to control when reloads happen.
- `write_disposition = "WRITE_TRUNCATE"` overwrites the table on every apply.
- `skip_leading_rows = 1` skips the CSV header row.

## Cleanup

```bash
terraform destroy
```

> `delete_contents_on_destroy = true` is set on the dataset, so all tables and data will be removed automatically.
