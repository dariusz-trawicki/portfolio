terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

module "network" {
  source      = "../../modules/network"
  name        = "demo"
  vpc_cidr    = "10.42.0.0/16"
  public_cidr = "10.42.1.0/24"
  az          = "${var.region}a"
}

module "compute" {
  source        = "../../modules/compute"
  name          = "demo"
  env           = "dev"
  vpc_id        = module.network.vpc_id
  subnet_id     = module.network.public_subnet_id
  instance_type = "t3.micro"
}
