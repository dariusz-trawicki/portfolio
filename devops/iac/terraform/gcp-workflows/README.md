# GCP - workflow with subworkflows:

- subworkflow_1 - create DBs
- subworkflow_2 - create users
- subworkflow_3 - delete DBs
- subworkflow_4 - delete users

## Two solutions:

1. Define and put workflow parameters values in `terraform` code - `workflow_tf_env_vars`

### RUN

- terraform:

```bash
terraform init
terraform apply
```

- GCP > Workflows > Execute: `workflow_tf_env_vars`

2. GCP > Workflows > Execute: Set the parameters values in `Input` section (pass a JSON object as input to the workflow) `workflow_input_object`

### RUN

- terraform:

```bash
terraform init
terraform apply
```

- GCP > Workflows > Execute: `workflow_input_object` with JSON input:

  - for `dbs operation`:

```json
{
  "operation": "create_sql_dbs",
  "dbs": ["db1", "db2", "db3"],
  "project_id": "sub-workflows-exp-91df",
  "sql_instance_name": "main"
}
```

```json
{
  "operation": "delete_sql_dbs",
  "dbs": ["db1", "db2", "db3"],
  "project_id": "sub-workflows-exp-91df",
  "sql_instance_name": "main"
}
```

    - for `users operation`:

```json
{
  "operation": "create_sql_users",
  "users": [
    {"name": "user1", "password": "password1"},
    {"name": "user2", "password": "password2"},
    {"name": "user3", "password": "password3"}
  ],
  "project_id": "sub-workflows-exp-91df",
  "sql_instance_name": "main"
}
```

```json
{
  "operation": "delete_sql_users",
  "users": [
    {"name": "user1", "password": "password1"},
    {"name": "user2", "password": "password2"},
    {"name": "user3", "password": "password3"}
  ],
  "project_id": "sub-workflows-exp-91df",
  "sql_instance_name": "main"
}
```
