resource "google_compute_global_address" "lb_ip" {
  name    = "public-lb-ip"
  project = module.project.project_id
}


resource "google_compute_region_network_endpoint_group" "cloud_run_neg" {
  name                  = "cloud-run-neg"
  network_endpoint_type = "SERVERLESS"
  project               = module.project.project_id
  region                = var.region

  cloud_run {
    service = module.cloud_run_service.service_name
  }
}


resource "google_compute_backend_service" "cloud_run_backend" {
  name                  = "cloud-run-backend"
  project               = module.project.project_id
  load_balancing_scheme = "EXTERNAL"
  protocol              = "HTTP"

  backend {
    group = google_compute_region_network_endpoint_group.cloud_run_neg.id
  }
}


resource "google_compute_url_map" "lb_url_map" {
  name            = "cloud-run-url-map"
  project         = module.project.project_id
  default_service = google_compute_backend_service.cloud_run_backend.self_link
}


resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "http-proxy"
  project = module.project.project_id
  url_map = google_compute_url_map.lb_url_map.self_link
}


resource "google_compute_global_forwarding_rule" "http_forwarding_rule" {
  name        = "http-forwarding-rule"
  project     = module.project.project_id
  target      = google_compute_target_http_proxy.http_proxy.self_link
  port_range  = "80"
  ip_address  = google_compute_global_address.lb_ip.address
  ip_protocol = "TCP"
}
