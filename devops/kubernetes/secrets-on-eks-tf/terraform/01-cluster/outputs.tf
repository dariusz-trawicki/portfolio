output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "region" {
  description = "AWS region."
  value       = var.region
}

output "secret_name" {
  description = "Secrets Manager secret name. Feed this into stage 02."
  value       = aws_secretsmanager_secret.db.name
}

output "eso_role_arn" {
  description = "IAM role assumed by the ESO controller."
  value       = aws_iam_role.eso.arn
}

output "kubeconfig_command" {
  description = "Run this before applying stage 02."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}
