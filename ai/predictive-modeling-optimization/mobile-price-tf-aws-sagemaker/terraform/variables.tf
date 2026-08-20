variable "region" {
  description = "AWS region where resources will be created"
  default     = "eu-central-1"
}

variable "bucket_name" {
  description = "Unique S3 bucket name for SageMaker project"
  default     = "dartit-sagemaker-123"
}

variable "role_name" {
  description = "IAM role name for SageMaker"
  default     = "sagemakeraccess"
}
