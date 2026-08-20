module "project" {
  source                  = "terraform-google-modules/project-factory/google"
  version                 = "~> 14.0"
  random_project_id       = true
  name                    = var.project_name
  org_id                  = var.org_id
  billing_account         = var.billing_account
  folder_id               = var.folder_id
  default_service_account = "keep"
  create_project_sa       = false

  activate_apis = [
    "run.googleapis.com",
  ]

  labels = {}

  disable_services_on_destroy = false

}
