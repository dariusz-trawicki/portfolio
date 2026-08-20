output "lambda_function_name" {
  value = aws_lambda_function.bedrock_blog.function_name
}

output "s3_bucket_name" {
  value = aws_s3_bucket.blog_bucket.bucket
}
