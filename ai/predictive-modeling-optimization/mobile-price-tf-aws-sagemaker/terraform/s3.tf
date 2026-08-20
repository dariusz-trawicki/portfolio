resource "aws_s3_bucket" "sagemaker" {
  bucket = var.bucket_name
}

