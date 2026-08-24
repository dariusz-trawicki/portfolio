variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "name" {
  description = "Name prefix applied to the cluster and all related resources."
  type        = string
  default     = "eso-lab"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane."
  type        = string
  default     = "1.32"
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes."
  type        = string
  default     = "t3.medium"
}

variable "enable_nat_gateway" {
  description = <<-EOT
    Place nodes in private subnets behind a NAT gateway.

    Set to false to save roughly $32/month: nodes then run in public subnets
    with public IPs. Acceptable for a short-lived lab, never for production.
  EOT
  type        = bool
  default     = true
}

variable "demo_password" {
  description = <<-EOT
    Placeholder value stored in Secrets Manager.

    This is a stand-in for a real credential and is NOT sensitive - it opens
    nothing. Real passwords should never be passed to Terraform this way.
  EOT
  type        = string
  default     = "initial-value-123"
}
