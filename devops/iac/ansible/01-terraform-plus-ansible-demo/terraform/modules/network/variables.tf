variable "name" {
  description = "Prefix for resource naming"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
}

variable "az" {
  description = "Availability Zone for the subnet"
  type        = string
}
