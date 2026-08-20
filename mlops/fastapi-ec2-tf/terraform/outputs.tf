output "public_ip" {
  value = aws_instance.fastapi.public_ip
}

output "api_url" {
  value = "http://${aws_instance.fastapi.public_ip}"
}

output "ssh_command" {
  value = "ssh -i fastapi-key.pem ubuntu@${aws_instance.fastapi.public_ip}"
}

output "docs_url" {
  value = "http://${aws_instance.fastapi.public_ip}/docs"
}
