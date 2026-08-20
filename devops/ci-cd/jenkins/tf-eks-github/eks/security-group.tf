resource "aws_security_group" "eks_nodes" {
  name        = "${local.name}-nodes-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  tags = merge(local.tags, {
    "kubernetes.io/cluster/${local.name}" = "owned"
  })
}
