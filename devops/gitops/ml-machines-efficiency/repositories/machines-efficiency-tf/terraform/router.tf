resource "google_compute_router" "router" {
  name    = "router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.main.id
}
