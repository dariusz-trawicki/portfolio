resource "google_container_cluster" "primary" {
  name                     = var.cluster_name
  project                  = var.project_id
  location                 = var.zone
  remove_default_node_pool = true
  initial_node_count       = 1
  network                  = google_compute_network.main.self_link
  subnetwork               = google_compute_subnetwork.private.self_link
  networking_mode          = "VPC_NATIVE"

  deletion_protection = false

  # Additional zone for a multi-zonal cluster.
  # NOTE: node_count on each pool is PER ZONE, so node_count = 1 runs 2 nodes.
  # Set var.zone2 = null for a single-zone cluster.
  node_locations = var.zone2 == null ? [] : [var.zone2]

  addons_config {
    # Disables the GKE Ingress controller. Fine for Service type LoadBalancer
    # (L4). Re-enable if you want Ingress + a Google-managed certificate.
    http_load_balancing {
      disabled = true
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  release_channel {
    channel = "REGULAR"
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "k8s-pod-range"
    services_secondary_range_name = "k8s-service-range"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Only rendered when the list is non-empty; an empty block would lock out
  # every address including yours.
  dynamic "master_authorized_networks_config" {
    for_each = length(var.master_authorized_cidrs) > 0 ? [1] : []
    content {
      dynamic "cidr_blocks" {
        for_each = var.master_authorized_cidrs
        content {
          cidr_block   = cidr_blocks.value.cidr_block
          display_name = cidr_blocks.value.display_name
        }
      }
    }
  }
}

resource "google_service_account" "kubernetes" {
  account_id = "kubernetes"
  project    = var.project_id

  depends_on = [time_sleep.wait]
}

resource "google_container_node_pool" "general" {
  name       = "general"
  project    = var.project_id
  cluster    = google_container_cluster.primary.id
  node_count = var.general_node_count

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    preemptible  = false
    machine_type = var.general_machine_type

    labels = {
      role = "general"
    }

    service_account = google_service_account.kubernetes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  # Nodes can otherwise boot before their service account may write logs and
  # metrics, producing a burst of permission errors on first start.
  depends_on = [
    google_project_iam_member.kubernetes_logging,
    google_project_iam_member.kubernetes_monitoring,
    google_project_iam_member.kubernetes_monitoring_viewer,
    google_artifact_registry_repository_iam_member.gke_reader,
  ]
}

# ---------------------------------------------------------------------------
# Spot pool.
#
# The NO_SCHEDULE taint means nothing lands here without a matching toleration,
# and the autoscaler will not scale up from 0 for pods that do not tolerate it.
# To actually use it, add to a Deployment:
#
#   tolerations:
#     - key: instance_type
#       operator: Equal
#       value: spot
#       effect: NoSchedule
#
# Do NOT run ArgoCD here - spot nodes are reclaimed with ~30s notice.
# ---------------------------------------------------------------------------
resource "google_container_node_pool" "spot" {
  name    = "spot"
  project = var.project_id
  cluster = google_container_cluster.primary.id

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  autoscaling {
    min_node_count = 0
    max_node_count = 10
  }

  node_config {
    preemptible  = true
    machine_type = var.spot_machine_type

    labels = {
      team = "devops"
    }

    taint {
      key    = "instance_type"
      value  = "spot"
      effect = "NO_SCHEDULE"
    }

    service_account = google_service_account.kubernetes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  depends_on = [
    google_project_iam_member.kubernetes_logging,
    google_project_iam_member.kubernetes_monitoring,
    google_project_iam_member.kubernetes_monitoring_viewer,
    google_artifact_registry_repository_iam_member.gke_reader,
  ]
}
