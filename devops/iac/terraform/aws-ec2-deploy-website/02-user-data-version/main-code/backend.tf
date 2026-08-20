terraform {
  backend "s3" {
    bucket = "tf-state-dt-123456789"
    key    = "terraform/backend" # path within the bucket (folder/file)
    region = "eu-central-1"
  }
}
