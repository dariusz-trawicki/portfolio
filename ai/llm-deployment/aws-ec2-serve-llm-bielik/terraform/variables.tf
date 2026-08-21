variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "name" {
  type    = string
  default = "bielik-serving"
}

variable "instance_type" {
  type    = string
  default = "g5.xlarge"
}

variable "root_volume_gb" {
  type    = number
  default = 64
}

variable "key_pair_name" {
  type    = string
  default = "bielik-key-pair"
}

variable "public_key_path" {
  type        = string
  description = "Path to SSH public key"
  default     = "/Users/USER_NAME/.ssh/KEY_FILE_NAME.pub"
}

variable "my_ip_cidr" {
  type        = string
  description = "Your public IP w CIDR"
  default     = "XXX.XXX.XXX.XXX/32"
}

variable "script_sh_path" {
  type        = string
  description = "Path to sh script to run on instance"
  default     = "./install_script.sh"
}
