generate "backend" {
  path = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents = <<EOF
terraform { 
  backend "gcs" { 
    bucket  = "terragrunt-state-bucket-1234" 
    prefix  = "${path_relative_to_include()}/terraform.tfstate" 
  } 
}
EOF
}
