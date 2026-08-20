variable "aws_account_id" {
  description = "root AWS Account ID"
  type        = string
  default     = "xxxxxxxxxxxxx"
}

variable "bucket_name" {
  type    = string
  default = "my-s3-bucket-name-2545685"
}

variable "lambda_function_name" {
  type    = string
  default = "export_rds_snapshot_to_s3"
}

variable "rds_instance_name" {
  type    = string
  default = "main123"
}

variable "db_name" {
  type    = string
  default = "db1"
}

variable "db_user_name" {
  type    = string
  default = "adminuser"
}

variable "db_user_pass" {
  type    = string
  default = "pass123908089"
}

variable "instance_class" {
  type    = string
  default = "db.t3.micro"
}
