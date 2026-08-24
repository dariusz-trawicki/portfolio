resource "aws_secretsmanager_secret" "db" {
  name = "${local.name}/orders-api/db"

  # Lab-only. AWS normally retains a deleted secret for 30 days and blocks
  # reusing its name, which breaks repeated destroy/apply cycles.
  # Production: leave at the default 30.
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id

  # JSON rather than a bare string, so fields can be added later
  # (username, host, port) without restructuring anything.
  secret_string = jsonencode({
    username = "orders_app"
    password = var.demo_password
  })
}
