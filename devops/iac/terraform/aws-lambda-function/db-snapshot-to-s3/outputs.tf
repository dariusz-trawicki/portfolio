output "s3_bucket_name" {
  value = aws_s3_bucket.backup_bucket.id
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}
