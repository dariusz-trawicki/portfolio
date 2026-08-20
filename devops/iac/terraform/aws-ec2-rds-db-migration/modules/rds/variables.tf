variable "rds_vpc" {
  type    = string
  default = "vpc-0a202eaf717486382"
}

variable "ec2_sg" {
  type = string
}

variable "subnet_ids" {
  type    = list(string)
  default = ["subnet-0df1e66e47b73c3df", "subnet-05ff19a16b112102d"]
}

variable "allocated_storage" {
  type = number
}

variable "db_name" {
  type = string
}

variable "engine" {
  type = string
}

variable "engine_version" {
  type = string
}

variable "instance_class" {
  type = string
}

variable "username" {
  type = string
}

variable "password" {
  type = string
}