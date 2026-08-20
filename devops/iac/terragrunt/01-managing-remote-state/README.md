# Managing Remote State in GCS with Terragrunt

#### Assumptions

- The `GCS` bucket `terragrunt-state-bucket-1234` already exists.
- You’re authenticated to GCP (e.g., `gcloud auth application-default login`).
- `Terraform` and `Terragrunt` are installed.

#### RUN

Option A — initialize `all modules` from a common parent:

```bash
terragrunt run-all init
```

Option B — initialize selected modules individually:

```bash
cd frontend-app
terragrunt init

cd ../mysql
terragrunt init
```
