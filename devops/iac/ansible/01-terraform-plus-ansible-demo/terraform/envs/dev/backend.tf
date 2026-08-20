terraform {
  backend "s3" {
    bucket         = "tf-state-ansible-exp-123" # name of your S3 bucket
    key            = "dev/terraform.tfstate"    # path to the state file inside the bucket
    region         = "eu-central-1"             # AWS region where the bucket is located
    dynamodb_table = "terraform-locks"          # DynamoDB table used for state locking
    encrypt        = true                       # enable server-side encryption (SSE-S3)
  }
}
