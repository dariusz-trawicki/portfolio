#############################
#  Local settings
#############################

# Sender address – MUST be allowed by SES (domain verified)
locals {
  ses_from_email = var.sender_address # "dariusz.trawicki@dartit.pl"
}

#############################
# IAM role for Lambda
#############################

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "lambda-sqs-ses-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Basic CloudWatch logs permissions
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Policy: SQS + SES
data "aws_iam_policy_document" "lambda_policy" {
  statement {
    sid    = "AllowSQS"
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]

    resources = [
      aws_sqs_queue.email_queue.arn
    ]
  }

  statement {
    sid    = "AllowSESSendEmail"
    effect = "Allow"

    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name   = "lambda-sqs-ses-policy"
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

#############################
# Lambda – code from ./lambda
#############################

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/send_email.py"
  output_path = "${path.module}/lambda/send_email.zip"
}

resource "aws_lambda_function" "send_email" {
  function_name = "send-email-from-sqs"
  role          = aws_iam_role.lambda_role.arn
  handler       = "send_email.handler"
  runtime       = "python3.12"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      SES_FROM_EMAIL = local.ses_from_email
    }
  }
}

######################################
# Mapping: SQS -> Lambda (Trigger)
#####################################

resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.email_queue.arn
  function_name    = aws_lambda_function.send_email.arn
  batch_size       = 10
  enabled          = true
}