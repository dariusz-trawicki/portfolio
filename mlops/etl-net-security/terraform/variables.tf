variable "aws_region" {
  description = "AWS region for S3"
  type        = string
  default     = "eu-central-1"
}

variable "training_bucket_name" {
  description = "S3 bucket name used as TRAINING_BUCKET_NAME in the project"
  type        = string
}

variable "environment" {
  description = "Environment tag"
  type        = string
  default     = "dev"
}

variable "training_user_name" {
  description = "IAM user name for training pipeline"
  type        = string
  default     = "networksecurity-training-user"
}
