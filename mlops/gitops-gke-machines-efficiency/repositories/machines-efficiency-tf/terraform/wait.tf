# Newly enabled APIs are eventually consistent - resources created immediately
# afterwards intermittently fail with "API not enabled". A short pause is the
# pragmatic fix.
resource "time_sleep" "wait" {
  create_duration = "60s"
  depends_on      = [google_project_service.enabled]
}
