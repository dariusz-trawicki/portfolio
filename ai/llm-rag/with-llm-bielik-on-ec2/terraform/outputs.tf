# output "instance_id" {
#   value = aws_instance.bielik.id
# }

output "public_ip" {
  value = aws_instance.bielik.public_ip
}

# output "ssh_command" {
#   value = "ssh -i ~/.ssh/<your_private_key> ubuntu@${aws_instance.bielik.public_ip}"
# }
