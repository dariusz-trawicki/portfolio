output "verification_commands" {
  description = "Run these in order. Each step depends on the previous one passing."
  value       = <<-EOT

    1. ESO is running (expect 3 pods: controller, cert-controller, webhook)
       kubectl get pods -n external-secrets

    2. AWS authentication works (expect STATUS: Valid)
       kubectl get secretstore aws -n ${var.app_namespace}
       ^ this is the real test of the Pod Identity + IAM chain from stage 01

    3. Secret is syncing (expect STATUS: SecretSynced, READY: True)
       kubectl get externalsecret orders-api -n ${var.app_namespace}

    4. The value landed in the cluster
       kubectl get secret orders-api-secret -n ${var.app_namespace} \
         -o jsonpath='{.data.DB_PASSWORD}' | base64 -d; echo

  EOT
}

output "reloader_enabled" {
  description = "Whether Reloader was installed."
  value       = var.enable_reloader
}
