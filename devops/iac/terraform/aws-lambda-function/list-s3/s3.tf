resource "aws_s3_bucket" "bucket" {
  bucket = "example-bucket-name-dfhfg7"
  tags = {
    Name        = "My bucket"
    Environment = "Dev"
  }
}