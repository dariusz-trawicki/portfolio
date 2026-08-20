data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "lambda_function.py"
  output_path = "lambda_function.zip"
}


resource "aws_lambda_function" "export_rds_backup" {
  function_name = var.lambda_function_name
  description   = "Function to export RDS snapshot backup in S3"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.9"
  handler       = "lambda_function.handler"
  memory_size   = 128
  timeout       = 300
  filename      = "lambda_function.zip"

  environment {
    variables = {
      DB_INSTANCE_ID = var.rds_instance_name
      KMS_KEY        = aws_kms_key.custom_key.arn
      IAM_ROLE       = aws_iam_role.s3_role.arn
      S3_BUCKET      = var.bucket_name
    }
  }
}
