variable "ami_id" {
  type    = string
  default = "ami-0a72753edf3e631b7"
}

variable "instance_type" {
  type    = string
  default = "t2.micro"
}

variable "subnet_id" {
  type    = string
  default = "subnet-0df1e66e47b73c3df"
}

variable "vpc_id" {
  type    = string
  default = "vpc-0a202eaf717486382"
}