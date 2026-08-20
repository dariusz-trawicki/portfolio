output "cr_id" {
  value = module.cloud_run_service.service_id
}

output "cr_uri" {
  value = module.cloud_run_service.service_url
}

output "url" {
  value = "http://${google_compute_global_address.lb_ip.address}"
}
