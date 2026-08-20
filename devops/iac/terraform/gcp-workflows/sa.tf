resource "time_sleep" "wait" {
  create_duration = "60s"
  depends_on      = [module.project]
}


resource "google_service_account" "account" {
  account_id   = "workflow-account"
  display_name = "Test Workflow Service"
  project      = module.project.project_id
  depends_on   = [time_sleep.wait]
}


resource "google_project_iam_member" "account_sql_admin" {
  role    = "roles/cloudsql.admin"
  member  = "serviceAccount:${google_service_account.account.email}"
  project = module.project.project_id
}
