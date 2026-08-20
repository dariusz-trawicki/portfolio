terraform {
  backend "s3" {
    bucket = "terraform-vpc-12345"
    key    = "vpc-dev/terraform.tfstate"
    region = "eu-central-1"
  }
}
