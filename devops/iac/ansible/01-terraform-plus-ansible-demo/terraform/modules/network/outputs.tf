output "vpc_id" {
  description = "The ID of the created VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_id" {
  description = "The ID of the created public subnet"
  value       = aws_subnet.public.id
}
