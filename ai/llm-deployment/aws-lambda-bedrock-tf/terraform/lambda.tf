# --- Lambda ZIP package ---
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# --- Lambda function ---
resource "aws_lambda_function" "bedrock_blog" {
  function_name = "bedrock-blog-generator"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = data.archive_file.lambda_zip.output_path
  timeout       = 60
  memory_size   = 512

  environment {
    variables = {
      BEDROCK_REGION = var.region
      MODEL_ID       = var.model_id
      S3_BUCKET      = aws_s3_bucket.blog_bucket.bucket
      S3_PREFIX      = "blog-output/"
    }
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}
