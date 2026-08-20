# Google-managed TLS certificate (free, auto-renewing)
# CRD installed by GKE automatically; validates domain ownership via HTTP-01
resource "kubernetes_manifest" "wordpress_cert" {
  count = var.enable_https ? 1 : 0

  manifest = {
    apiVersion = "networking.gke.io/v1"
    kind       = "ManagedCertificate"
    metadata = {
      name      = "wordpress-cert"
      namespace = "default"
    }
    spec = {
      domains = var.wordpress_domains
    }
  }

  depends_on = [
    google_container_node_pool.primary_nodes,
  ]
}

# GCE Ingress - creates HTTPS Load Balancer with the managed cert attached
# Uses the reserved global static IP via annotation
resource "kubernetes_ingress_v1" "wordpress" {
  count = var.enable_https ? 1 : 0

  metadata {
    name      = "wordpress-ingress"
    namespace = "default"
    annotations = {
      # Pin to reserved static IP (must match google_compute_global_address.wordpress_ip)
      "kubernetes.io/ingress.global-static-ip-name" = google_compute_global_address.wordpress_ip.name

      # Attach the managed certificate
      "networking.gke.io/managed-certificates" = "wordpress-cert"

      # Use the GCE Ingress controller (creates HTTPS LB)
      "kubernetes.io/ingress.class" = "gce"

      # Disable plain HTTP - force HTTPS only.
      # Set to "true" temporarily if you need HTTP for debugging.
      "kubernetes.io/ingress.allow-http" = "false"
    }
  }

  spec {
    default_backend {
      service {
        name = kubernetes_service.wordpress.metadata[0].name
        port {
          number = 80
        }
      }
    }
  }

  depends_on = [
    kubernetes_manifest.wordpress_cert,
    kubernetes_service.wordpress,
  ]
}

resource "kubernetes_manifest" "wordpress_backendconfig" {
  count = var.enable_https ? 1 : 0

  manifest = {
    apiVersion = "cloud.google.com/v1"
    kind       = "BackendConfig"
    metadata = {
      name      = "wordpress-backendconfig"
      namespace = "default"
    }
    spec = {
      healthCheck = {
        type               = "HTTP"
        requestPath        = "/readme.html"
        checkIntervalSec   = 30
        timeoutSec         = 5
        healthyThreshold   = 1
        unhealthyThreshold = 2
      }
    }
  }

  depends_on = [google_container_node_pool.primary_nodes]
}
