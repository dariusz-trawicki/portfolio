resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "blog_bucket" {
  bucket = "dartit-bedrock-blog-${random_id.suffix.hex}"

  tags = {
    Name        = "bedrock-blog-bucket"
    Environment = "demo"
  }
}
