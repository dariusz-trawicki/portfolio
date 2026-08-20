resource "aws_db_instance" "main" {
  allocated_storage         = 10
  identifier                = var.rds_instance_name
  db_name                   = var.db_name
  engine                    = "postgres"
  engine_version            = "16.4"
  instance_class            = var.instance_class
  username                  = var.db_user_name
  password                  = var.db_user_pass
  skip_final_snapshot       = false
  final_snapshot_identifier = "${terraform.workspace}-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  storage_encrypted         = true

  backup_retention_period = 5
  backup_window           = "07:00-09:00"

  maintenance_window = "Tue:05:00-Tue:07:00"

  publicly_accessible = true
}
