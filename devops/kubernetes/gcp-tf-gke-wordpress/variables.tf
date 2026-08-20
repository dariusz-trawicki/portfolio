/**
 * Variable declarations
 */

# --- Required ---
variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "sql_user_name" {
  type        = string
  description = "MySQL user name for WordPress"
}

# --- Location ---
variable "region" {
  type        = string
  default     = "europe-central2"
  description = "GCP region (default: Warsaw)"
}

variable "zone" {
  type        = string
  default     = "europe-central2-a"
  description = "GCP zone for the GKE cluster"
}

# --- GKE Cluster ---
variable "cluster_name" {
  type    = string
  default = "wordpress-cluster"
}

variable "gke_node_sa_name" {
  type        = string
  default     = "gke-service-account"
  description = "Name (6-30 chars) for the GKE node Service Account"
}

variable "gke_num_nodes" {
  type        = number
  default     = 1
  description = "Number of nodes in the GKE node pool"
}

variable "machine_type" {
  type        = string
  default     = "n1-standard-1"
  description = "GKE node machine type (run `gcloud compute machine-types list` to see options)"
}

variable "kubernetes_service_account_name" {
  type        = string
  default     = "kubernetes-service-account"
  description = "Name (6-30 chars) for the Kubernetes Service Account bound via Workload Identity"
}

variable "wordpress_app_sa_name" {
  type        = string
  default     = "wordpress-service-account"
  description = "Name (6-30 chars) for the WordPress app GCP Service Account"
}

# --- Cloud SQL ---
variable "sql_instance_name" {
  type    = string
  default = "mysql-wb-instance"
}

variable "sql_database_name" {
  type    = string
  default = "mysql-wb-db"
}

variable "sql_database_version" {
  type    = string
  default = "MYSQL_8_0"
}

variable "sql_tier" {
  type        = string
  default     = "db-f1-micro"
  description = "Cloud SQL tier (run `gcloud sql tiers list` for available options)"
}

# --- WordPress storage ---
variable "wp_storage_size_gb" {
  type        = number
  default     = 4
  description = "Persistent volume size in GB for /var/www/html/wp-content"
}

# --- HTTPS (Stage 2) ---
variable "enable_https" {
  type        = bool
  default     = false
  description = <<-EOT
    Toggles HTTPS Ingress and Google-managed Certificate.

    Stage 1 (false): LoadBalancer Service with ephemeral public IP. Use for initial deploy.
    Stage 2 (true): NodePort Service + Ingress + ManagedCertificate. Use after DNS points to static_ip.

    DO NOT set to true on the first apply - cluster must exist for kubernetes_manifest to work.
  EOT
}

variable "wordpress_domains" {
  type        = list(string)
  default     = []
  description = <<-EOT
    List of domains for the managed certificate, e.g. ["example.com", "www.example.com"].
    First domain is used as the primary (set as WP_HOME and WP_SITEURL in WordPress).
    Required when enable_https = true.
  EOT
}
