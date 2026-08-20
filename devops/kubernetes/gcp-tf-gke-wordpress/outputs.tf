/**
 * Outputs
 */

output "static_ip" {
  value       = google_compute_global_address.wordpress_ip.address
  description = "Reserved global static IP. Use this as the DNS A record target for your domain(s)."
}

output "sql_instance_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL instance connection name (used by the proxy sidecar)"
}

output "generated_sql_password" {
  value       = random_password.sql_user_password.result
  sensitive   = true
  description = "Auto-generated MySQL password. Reveal with: terraform output -raw generated_sql_password"
}

output "loadbalancer_ip" {
  value = (
    var.enable_https
    ? null
    : try(kubernetes_service.wordpress.status[0].load_balancer[0].ingress[0].ip, null)
  )
  description = "Ephemeral L4 LoadBalancer IP - populated only when enable_https=false. Use it to test the site before enabling HTTPS."
}

output "next_steps" {
  value = (
    var.enable_https
    ? "HTTPS enabled. Wait 15-60 min for cert provisioning.\nMonitor: kubectl describe managedcertificate wordpress-cert\nThen open: https://${try(var.wordpress_domains[0], "<domain>")}"
    : "Stage 1 deployed. Next:\n  1. Configure DNS A records pointing to ${google_compute_global_address.wordpress_ip.address}:\n     ${join(", ", var.wordpress_domains)}\n  2. Verify with: dig ${try(var.wordpress_domains[0], "<your-domain>")}\n  3. Set enable_https=true in terraform.tfvars and run: terraform apply"
  )
  description = "What to do next based on the current stage"
}
