variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "env" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.42.1.0/24"
}

variable "az" {
  description = "Availability zone for subnet"
  type        = string
  default     = "eu-central-1a"
}

variable "instance_type" {
  description = "Instance type for EC2 web nodes"
  type        = string
  default     = "t3.micro"
}
