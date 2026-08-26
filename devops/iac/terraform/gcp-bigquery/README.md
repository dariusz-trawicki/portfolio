# BigQuery CSV Loader

A Terraform demo that creates a BigQuery dataset, table, and loads data from a local CSV file via GCS.

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

- **The code**:
  - [`gcp-bigquery`](https://github.com/dariusz-trawicki/portfolio/tree/main/data-engineering/gcp-bigquery)
