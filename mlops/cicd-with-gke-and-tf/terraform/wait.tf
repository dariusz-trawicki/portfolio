resource "time_sleep" "wait" {
  create_duration = "60s"
  depends_on      = [module.project]
}
