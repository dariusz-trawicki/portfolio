resource "aws_s3_bucket" "backup_bucket" {
  bucket = var.bucket_name

  force_destroy = true
}
