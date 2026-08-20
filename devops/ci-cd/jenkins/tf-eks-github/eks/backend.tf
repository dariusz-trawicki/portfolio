terraform {
  backend "s3" {
    bucket = "terraform-jenkins-eks-12345"
    key    = "eks/terraform.tfstate"
    region = "eu-central-1"
  }
}