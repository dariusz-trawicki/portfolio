# SSH only through Identity-Aware Proxy, and only for instances tagged
# "ssh-enabled". There are no VMs in this configuration today; the rule exists
# so adding one later does not open port 22 to the internet.
# Delete this file if you never plan to add a VM.
resource "google_compute_firewall" "allow_ssh_iap" {
  name    = "allow-ssh-iap"
  project = var.project_id
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"] # IAP TCP forwarding
  target_tags   = ["ssh-enabled"]
}
