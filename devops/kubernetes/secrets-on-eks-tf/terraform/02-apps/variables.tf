variable "region" {
  description = "AWS region. Must match stage 01."
  type        = string
  default     = "eu-central-1"
}

variable "cluster_name" {
  description = "EKS cluster name from stage 01."
  type        = string
  default     = "eso-lab"
}

variable "secret_name" {
  description = "Secrets Manager secret name from stage 01 (its `secret_name` output)."
  type        = string
  default     = "eso-lab/orders-api/db"
}

variable "app_namespace" {
  description = "Namespace holding the SecretStore, ExternalSecret and demo app."
  type        = string
  default     = "default"
}

variable "refresh_interval" {
  description = <<-EOT
    How often ESO re-reads the secret from AWS.

    Shorter intervals cost more: Secrets Manager bills per API call, and the
    cost scales with (number of ExternalSecrets / interval). One hour is a
    sensible default for static secrets.
  EOT
  type        = string
  default     = "1h"
}

variable "eso_chart_version" {
  description = "Pinned External Secrets Operator chart version. null tracks latest."
  type        = string
  default     = null
}

variable "enable_reloader" {
  description = <<-EOT
    Install Stakater Reloader to restart pods when their Secret changes.

    Left off by default so the rotation gap can be demonstrated first
    (see "The rotation gap" in the README).
  EOT
  type        = bool
  default     = false
}
