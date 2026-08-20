output "s3_bucket_name" {
  value = aws_s3_bucket.sagemaker.bucket
}

output "sagemaker_iam_role_arn" {
  value = aws_iam_role.sagemakeraccess.arn
}