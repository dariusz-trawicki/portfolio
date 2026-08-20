terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}


# -----------------------------
# S3 BUCKET FOR TRAINING ARTIFACTS
# -----------------------------
resource "aws_s3_bucket" "training_bucket" {
  bucket = var.training_bucket_name

  tags = {
    Name        = var.training_bucket_name
    Environment = var.environment
    Project     = "network-security-mlops"
  }
}


# -----------------------------
# IAM USER / ROLE FOR PIPELINE
# -----------------------------
resource "aws_iam_user" "training_user" {
  name = var.training_user_name

  tags = {
    Project = "network-security-mlops"
  }
}


resource "aws_iam_access_key" "training_user_key" {
  user = aws_iam_user.training_user.name
}


data "aws_iam_policy_document" "training_bucket_policy" {
  statement {
    sid    = "AllowBucketList"
    effect = "Allow"

    actions = [
      "s3:ListBucket"
    ]

    resources = [
      aws_s3_bucket.training_bucket.arn
    ]
  }

  statement {
    sid    = "AllowObjectRW"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.training_bucket.arn}/*"
    ]
  }
}


resource "aws_iam_policy" "training_bucket_policy" {
  name   = "${var.training_bucket_name}-access-policy"
  policy = data.aws_iam_policy_document.training_bucket_policy.json
}


resource "aws_iam_user_policy_attachment" "training_user_attach" {
  user       = aws_iam_user.training_user.name
  policy_arn = aws_iam_policy.training_bucket_policy.arn
}


# # -----------------------------
# # OUTPUTS
# # -----------------------------
# output "training_bucket_name" {
#   value = aws_s3_bucket.training_bucket.id
# }

# output "training_bucket_arn" {
#   value = aws_s3_bucket.training_bucket.arn
# }

# output "training_user_access_key_id" {
#   value       = aws_iam_access_key.training_user_key.id
#   description = "Use as AWS_ACCESS_KEY_ID"
# }

# output "training_user_secret_access_key" {
#   value       = aws_iam_access_key.training_user_key.secret
#   description = "Use as AWS_SECRET_ACCESS_KEY"
#   sensitive   = true
# }
