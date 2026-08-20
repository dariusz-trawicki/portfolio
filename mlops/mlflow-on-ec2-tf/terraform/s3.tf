resource "aws_s3_bucket" "mlflow" {
  bucket = var.bucket_name
  tags = {
    project = "mlflow"
  }
}
resource "aws_s3_bucket_public_access_block" "mlflow" {
  bucket                  = aws_s3_bucket.mlflow.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow" {
  bucket = aws_s3_bucket.mlflow.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
