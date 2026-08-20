data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_policy" "s3_policy" {
  name        = var.policy_name
  description = "S3 full Access"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:*",
        ]
        Effect   = "Allow"
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role" "iam_for_lambda" {
  name                = var.role_name
  assume_role_policy  = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy_attachment" "s3_policy_attachment" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.s3_policy.arn
  depends_on = [ aws_iam_role.iam_for_lambda ]
}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = var.source_function_file_name
  output_path = "lambda_function.zip"
}

resource "aws_lambda_function" "test_lambda" {
  filename      = data.archive_file.lambda.output_path
  function_name = var.lambda_function_name
  role          = aws_iam_role.iam_for_lambda.arn
  # cut extension of the source function file name
  handler       = "${join("", slice(split(".", var.source_function_file_name), 0, 1))}.${var.source_function_name}"

  source_code_hash = data.archive_file.lambda.output_base64sha256

  runtime = "python3.11"

  environment {
    variables = {
      foo = "bar"
    }
  }
}