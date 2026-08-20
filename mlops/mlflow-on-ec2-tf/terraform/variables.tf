variable "region" {
  description = "AWS region where resources will be created"
  default     = "eu-central-1"
}

variable "bucket_name" {
  description = "Unique S3 bucket name for MLflow artifacts"
  default     = "dartit-mlflow-bucket-10-2025"
}

variable "key_name" {
  description = "Existing EC2 key pair for SSH login"
  default     = "mlflow-key"
}

variable "instance_type" {
  description = "Type of EC2 instance"
  # default     = "t3.micro"
  default = "t3.large"
}

# For security, replace 0.0.0.0/0
variable "allowed_cidr" {
  description = "IP address range allowed to access (e.g. 203.0.113.25/32)"
  default     = "0.0.0.0/0"
}
