terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # In a real project, use a remote backend. Local state is fine for a
  # throwaway lab, but it holds the secret value in plaintext (see secret.tf).
  #
  # backend "s3" {
  #   bucket         = "my-tfstate-bucket"
  #   key            = "eso-demo/01-cluster/terraform.tfstate"
  #   region         = "eu-central-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}

locals {
  name = var.name
}

data "aws_availability_zones" "available" {
  state = "available"
}

################################################################################
# Networking
################################################################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  # Nodes live in private subnets and reach the internet through NAT.
  # A single NAT gateway is a deliberate cost trade-off for a lab: it is a
  # single point of failure, but costs ~$32/month instead of ~$64.
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = true
  enable_dns_hostnames = true

  # EKS discovers subnets by these tags when provisioning load balancers.
  # Without them, a Service of type LoadBalancer silently fails to schedule.
  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

################################################################################
# EKS cluster
################################################################################

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = local.name
  cluster_version = var.cluster_version

  vpc_id = module.vpc.vpc_id

  # If NAT is disabled to save money, nodes go in public subnets so they can
  # still pull images. Acceptable for a lab, never for production.
  subnet_ids = var.enable_nat_gateway ? module.vpc.private_subnets : module.vpc.public_subnets

  cluster_endpoint_public_access = true

  # Grants the IAM principal running `terraform apply` cluster-admin.
  # Without it, `kubectl get nodes` returns Unauthorized after apply.
  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}

    # Installs a DaemonSet on every node that hands short-lived AWS
    # credentials to pods. This is what lets ESO call Secrets Manager
    # without any static access key.
    eks-pod-identity-agent = {}
  }

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      min_size       = 2
      max_size       = 3
      desired_size   = 2
    }
  }
}
