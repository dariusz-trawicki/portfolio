resource "google_workflows_workflow" "workflow_tf_env_vars" {
  name            = "subworkflows-with-tf-parameters"
  region          = var.region
  description     = "create, delete for db and user"
  project         = module.project.project_id
  service_account = google_service_account.account.id
  call_log_level  = "LOG_ERRORS_ONLY"

  # resource group label: environment name
  labels = {
    env = "test"
  }

  user_env_vars = {
    project_name      = module.project.project_name
    project_id        = module.project.project_id
    sql_instance_name = google_sql_database_instance.instance.name
    dbs               = jsonencode(var.dbs)
    users             = jsonencode(var.users)
  }

  source_contents = file("workflow_tf_env_vars.yaml")

  depends_on = [
    google_service_account.account,
  ]
}

resource "google_workflows_workflow" "workflow_input_object" {
  name            = "subworkflows-with-input-object"
  region          = var.region
  description     = "create, delete for db and user"
  project         = module.project.project_id
  service_account = google_service_account.account.id
  call_log_level  = "LOG_ERRORS_ONLY"

  # resource group label: environment name
  labels = {
    env = "test"
  }

  source_contents = file("workflow_input_object.yaml")

  depends_on = [
    google_service_account.account,
  ]
}
