output "argocd_port_forward" {
  value = "kubectl port-forward svc/argocd-server -n argocd 8080:80"
}

output "argocd_admin_password_command" {
  value = "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
}
