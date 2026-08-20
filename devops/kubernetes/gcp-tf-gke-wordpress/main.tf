# --- Enable Google Cloud APIs ---
resource "google_project_service" "required_apis" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false # APIs are free, don't try to disable them on destroy
}

# --- IAM Service Accounts ---

# Service Account for GKE Nodes (minimal permissions)
resource "google_service_account" "gke_node_sa" {
  project      = var.project_id
  account_id   = var.gke_node_sa_name
  display_name = "GKE Node SA (${var.cluster_name})"
  depends_on   = [google_project_service.required_apis]
}

resource "google_project_iam_member" "gke_node_sa_roles" {
  for_each = toset([
    "roles/monitoring.viewer",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

# Service Account for WordPress App (Workload Identity)
resource "google_service_account" "wordpress_app_sa" {
  project      = var.project_id
  account_id   = var.wordpress_app_sa_name
  display_name = "WordPress App SA (${var.cluster_name})"
  depends_on   = [google_project_service.required_apis]
}

resource "google_project_iam_member" "wordpress_app_sa_sqlclient" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.wordpress_app_sa.email}"
}

# Bind KSA to GSA via Workload Identity
# IMPORTANT: depends on cluster - identity pool is created with the cluster
resource "google_service_account_iam_member" "wordpress_ksa_wi_binding" {
  service_account_id = google_service_account.wordpress_app_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[default/${var.kubernetes_service_account_name}]"
  depends_on = [
    google_service_account.wordpress_app_sa,
    google_container_cluster.primary,
    google_container_node_pool.primary_nodes,
  ]
}

# --- GKE Cluster ---
resource "google_container_cluster" "primary" {
  project                  = var.project_id
  name                     = var.cluster_name
  location                 = var.zone
  remove_default_node_pool = true
  initial_node_count       = 1

  # network_policy {
  #   enabled = true
  # }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  deletion_protection = false
  depends_on          = [google_project_service.required_apis]
}

resource "google_container_node_pool" "primary_nodes" {
  project    = var.project_id
  name       = "${var.cluster_name}-node-pool"
  location   = google_container_cluster.primary.location
  cluster    = google_container_cluster.primary.name
  node_count = var.gke_num_nodes

  node_config {
    machine_type    = var.machine_type
    service_account = google_service_account.gke_node_sa.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  depends_on = [google_service_account.gke_node_sa]
}

# --- Cloud SQL Instance ---
resource "random_password" "sql_user_password" {
  length  = 16
  special = false
}

resource "google_sql_database_instance" "main" {
  project          = var.project_id
  name             = var.sql_instance_name
  database_version = var.sql_database_version
  region           = var.region
  settings {
    tier = var.sql_tier
    ip_configuration {
      ipv4_enabled = true
    }
    backup_configuration {
      enabled = false
    }
  }
  deletion_protection = false
  depends_on          = [google_project_service.required_apis]
}

resource "google_sql_database" "database" {
  project  = var.project_id
  name     = var.sql_database_name
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "user" {
  project  = var.project_id
  name     = var.sql_user_name
  instance = google_sql_database_instance.main.name
  password = random_password.sql_user_password.result
}

# --- Global Static IP for HTTPS Ingress ---
# Reserved in stage 1, attached to Ingress in stage 2.
# Use this IP as the DNS A record target.
resource "google_compute_global_address" "wordpress_ip" {
  project    = var.project_id
  name       = "wordpress-static-ip"
  depends_on = [google_project_service.required_apis]
}

# --- Kubernetes Provider Configuration ---
data "google_container_cluster" "cluster_data" {
  project    = var.project_id
  name       = google_container_cluster.primary.name
  location   = google_container_cluster.primary.location
  depends_on = [google_container_node_pool.primary_nodes]
}


# --- Kubernetes Resources ---
resource "kubernetes_service_account" "wordpress_ksa" {
  metadata {
    name      = var.kubernetes_service_account_name
    namespace = "default"
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.wordpress_app_sa.email
    }
  }
  depends_on = [google_service_account_iam_member.wordpress_ksa_wi_binding]
}

# Secret with DB credentials (including password - fixed from original)
resource "kubernetes_secret" "db_details" {
  metadata {
    name      = "wordpress-db-details"
    namespace = "default"
  }
  data = {
    DB_NAME     = google_sql_database.database.name
    DB_USER     = google_sql_user.user.name
    DB_PASSWORD = random_password.sql_user_password.result
  }
  type       = "Opaque"
  depends_on = [google_sql_user.user]
}

# PersistentVolumeClaim - using typed resource (not kubernetes_manifest)
resource "kubernetes_persistent_volume_claim_v1" "wp_pvc" {
  metadata {
    name      = "wp-pv-claim"
    namespace = "default"
    labels = {
      app = "wordpress"
    }
  }
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "standard-rwo"
    resources {
      requests = {
        storage = "${var.wp_storage_size_gb}Gi"
      }
    }
  }
  # PVC won't bind until a Pod uses it (GKE default behavior)
  wait_until_bound = false
}

# WordPress Deployment with sidecar Cloud SQL Proxy
resource "kubernetes_deployment" "wordpress" {
  metadata {
    name      = "wordpress"
    namespace = "default"
    labels    = { app = "wordpress" }
  }

  spec {
    replicas = 1

    # Recreate (not RollingUpdate) - required because PVC is ReadWriteOnce.
    # Rolling update deadlocks: new Pod can't mount volume held by old Pod.
    strategy {
      type = "Recreate"
    }

    selector { match_labels = { app = "wordpress" } }

    template {
      metadata { labels = { app = "wordpress" } }

      spec {
        service_account_name = kubernetes_service_account.wordpress_ksa.metadata[0].name

        container {
          name  = "wordpress"
          image = "wordpress:latest"

          port {
            container_port = 80
            name           = "http"
          }

          env {
            name  = "WORDPRESS_DB_HOST"
            value = "127.0.0.1:3306"
          }
          env {
            name = "WORDPRESS_DB_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.db_details.metadata[0].name
                key  = "DB_USER"
              }
            }
          }
          env {
            name = "WORDPRESS_DB_NAME"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.db_details.metadata[0].name
                key  = "DB_NAME"
              }
            }
          }
          env {
            name = "WORDPRESS_DB_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.db_details.metadata[0].name
                key  = "DB_PASSWORD"
              }
            }
          }

          # HTTPS-aware config: only injected when enable_https = true.
          # Tells WordPress its public URL is HTTPS and to detect TLS termination
          # at the GCP HTTPS Load Balancer via X-Forwarded-Proto header.
          # $$ is Terraform's escape for literal $ in PHP code.
          dynamic "env" {
            for_each = var.enable_https && length(var.wordpress_domains) > 0 ? [1] : []
            content {
              name  = "WORDPRESS_CONFIG_EXTRA"
              value = <<-EOT
                define('WP_HOME', 'https://${var.wordpress_domains[0]}');
                define('WP_SITEURL', 'https://${var.wordpress_domains[0]}');
                if (isset($$_SERVER['HTTP_X_FORWARDED_PROTO']) && $$_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
                    $$_SERVER['HTTPS'] = 'on';
                }
              EOT
            }
          }

          volume_mount {
            name       = "wordpress-persistent-storage"
            mount_path = "/var/www/html/wp-content"
          }
        }

        # Cloud SQL Auth Proxy sidecar - authenticated via Workload Identity
        container {
          name  = "cloud-sql-proxy"
          image = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.1"
          args  = ["--structured-logs", "--port=3306", google_sql_database_instance.main.connection_name]

          security_context {
            run_as_non_root = true
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
          }
        }

        volume {
          name = "wordpress-persistent-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.wp_pvc.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_service_account.wordpress_ksa,
    kubernetes_secret.db_details,
    kubernetes_persistent_volume_claim_v1.wp_pvc,
  ]
}

# WordPress Service
# Stage 1 (enable_https=false): LoadBalancer with ephemeral public IP
# Stage 2 (enable_https=true): NodePort - traffic comes through Ingress instead
resource "kubernetes_service" "wordpress" {
  # metadata {
  #   name      = "wordpress"
  #   namespace = "default"
  #   labels    = { app = "wordpress" }
  # }

  # metadata {
  #   name = "wordpress"
  #   annotations = var.enable_https ? {
  #     "cloud.google.com/backend-config" = jsonencode({ default = "wordpress-backendconfig" })
  #   } : {}
  # }

  metadata {
    name      = "wordpress"
    namespace = "default"
    labels    = { app = "wordpress" }

    annotations = var.enable_https ? {
      "cloud.google.com/backend-config" = jsonencode({ default = "wordpress-backendconfig" })
    } : {}
  }

  spec {
    selector = { app = "wordpress" }

    port {
      port     = 80
      protocol = "TCP"
      name     = "http"
    }

    type = var.enable_https ? "NodePort" : "LoadBalancer"
  }
  depends_on = [kubernetes_deployment.wordpress]
}
