module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name                   = local.name
  cluster_endpoint_public_access = true

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.public_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets

  node_security_group_id = aws_security_group.eks_nodes.id

  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }

  eks_managed_node_group_defaults = {
    ami_type                              = "AL2023_x86_64_STANDARD"
    instance_types                        = ["t3.large"]
    attach_cluster_primary_security_group = false
  }

  eks_managed_node_groups = {
    ascode-cluster-wg = {
      min_size      = 1
      max_size      = 2
      desired_size  = 1
      capacity_type = "SPOT"
    }
  }

  tags = local.tags
}
