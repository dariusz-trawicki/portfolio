output "WebPublicIP" {
  description = "AMI ID of Ubuntu instance"
  value       = aws_instance.web.public_ip
}

output "WebPrivateIP" {
  description = "AMI ID of Ubuntu instance"
  value       = aws_instance.web.private_ip
}