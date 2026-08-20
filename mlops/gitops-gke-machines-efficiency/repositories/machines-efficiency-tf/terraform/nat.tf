# Private nodes have no external IP, so all egress (pulling base images,
# reaching GitHub) goes through this NAT. MANUAL_ONLY with a reserved address
# gives a stable outbound IP you can allow-list elsewhere.
resource "google_compute_router_nat" "nat" {
  name    = "nat"
  project = var.project_id
  router  = google_compute_router.router.name
  region  = var.region

  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  nat_ip_allocate_option             = "MANUAL_ONLY"

  subnetwork {
    name                    = google_compute_subnetwork.private.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  nat_ips = [google_compute_address.nat.self_link]
}

resource "google_compute_address" "nat" {
  name         = "nat"
  project      = var.project_id
  region       = var.region
  address_type = "EXTERNAL"
  network_tier = "PREMIUM"

  depends_on = [time_sleep.wait]
}
