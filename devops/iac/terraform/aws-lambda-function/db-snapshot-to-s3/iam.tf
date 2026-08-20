# Create role IAM for eksport RDS to S3
resource "aws_iam_role" "s3_role" {
  name = "s3-export-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "export.rds.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

# Create politic IAM for S3
resource "aws_iam_policy" "s3_policy" {
  name        = "ExportBackupPolicy2"
  description = "Policy to allow RDS to export snapshots to S3"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:GetBucketLocation"
      ],
      Resource = [
        "arn:aws:s3:::${var.bucket_name}",
        "arn:aws:s3:::${var.bucket_name}/*"
      ]
    }]
  })
}

# Assigning a policy to a role
resource "aws_iam_role_policy_attachment" "s3_policy_attach" {
  role       = aws_iam_role.s3_role.name
  policy_arn = aws_iam_policy.s3_policy.arn
}


# Creating an IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda-rds-snapshot-to-s3-policy2"
  description = "Policy to allow Lambda to interact with RDS and KMS for snapshot exports"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusterSnapshots",
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances",
          "rds:DescribeDBSnapshots",
          "rds:DescribeExportTasks",
          "rds:StartExportTask",
          "iam:PassRole",
          "rds:CopyDBSnapshot"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*",
          "kms:CreateGrant"
        ]
        Resource = aws_kms_key.custom_key.arn
      }
    ]
  })
  depends_on = [
    aws_kms_key.custom_key
  ]
}


# Assigning a policy to a Lambda role
resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
