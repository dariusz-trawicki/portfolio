# --- IAM Role + Instance Profile (dostęp tylko do tego bucketu) ---
data "aws_iam_policy_document" "assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "ec2_role" {
  name               = "mlflow-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}
data "aws_iam_policy_document" "s3_bucket_rw" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.mlflow.arn]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.mlflow.arn}/*"]
  }
}
resource "aws_iam_policy" "s3_bucket_rw" {
  name   = "mlflow-s3-rw-${var.bucket_name}"
  policy = data.aws_iam_policy_document.s3_bucket_rw.json
}
resource "aws_iam_role_policy_attachment" "attach_bucket_rw" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_bucket_rw.arn
}
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "mlflow-ec2-profile"
  role = aws_iam_role.ec2_role.name
}
