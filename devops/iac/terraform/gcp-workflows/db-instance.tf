resource "google_sql_database_instance" "instance" {
  name             = var.instance_name
  database_version = var.db_version
  project          = module.project.project_id
  region           = var.region

  settings {
    tier = var.tier
    backup_configuration {
      enabled    = true
      start_time = "01:00" # start time of the daily backup
    }
  }

  deletion_protection = false
}
