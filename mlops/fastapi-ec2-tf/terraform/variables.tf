variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "ami" {
  description = "Ubuntu 22.04 LTS (eu-central-1)"
  type        = string
  default     = "ami-0faab6bdbac9486fb"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}
