variable "region" {
  type        = string
  description = "AWS region (e.g., eu-central-1)."
  default     = "eu-central-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-\\d$", var.region))
    error_message = "Use a valid AWS region like eu-central-1."
  }
}

variable "zone1" {
  type        = string
  description = "Preferred Availability Zone within aws_region (e.g., eu-central-1a)."
  default     = "eu-central-1a"
  validation {
    condition     = startswith(var.zone1, var.region) && length(var.zone1) > length(var.region)
    error_message = "AZ must belong to the same region, e.g., eu-central-1a."
  }
}

variable "aws_key_pair_name" {
  type        = string
  description = "Name of the EC2 key pair to create (in the target AWS region)."
  validation {
    condition     = length(var.aws_key_pair_name) > 0 && can(regex("^[A-Za-z0-9._-]+$", var.aws_key_pair_name))
    error_message = "Provide a non-empty EC2 key pair name (letters, digits, ., _, -)."
  }
}


variable "private_key_path" {
  type        = string
  description = "Path to the local PRIVATE SSH key (e.g., ~/.ssh/test-key)."
  sensitive   = true
  validation {
    condition     = length(var.private_key_path) > 0 && can(regex("^[/~A-Za-z0-9._-]+$", var.private_key_path))
    error_message = "Provide a non-empty path; allowed chars: letters, digits, /, ~, ., _, -."
  }
}


variable "project_name" {
  type        = string
  description = "Project name for tagging resources."
  default     = ""
  validation {
    condition     = length(var.project_name) > 0 && length(var.project_name) <= 128
    error_message = "Project name must be between 1 and 128 characters."
  }
}


variable "instance_name" {
  type        = string
  description = "Name tag for the EC2 instance."
  default     = ""
  validation {
    condition     = length(var.instance_name) > 0 && length(var.instance_name) <= 128
    error_message = "Instance name must be between 1 and 128 characters."
  }
}


variable "sg_name" {
  type        = string
  description = "Security Group name."
  default     = ""
}


variable "ssh_user" {
  type        = string
  description = "SSH username for the AMI (ubuntu for Ubuntu, ec2-user for Amazon Linux)."
  default     = ""
}


variable "ami_id" {
  type        = string
  description = "Pinned AMI ID for the chosen region (e.g., Ubuntu 22.04 LTS in eu-central-1)."
  default     = ""
  validation {
    condition     = can(regex("^ami-[0-9a-f]{8,}$", var.ami_id))
    error_message = "AMI must look like ami-xxxxxxxx or ami-xxxxxxxxxxxxxxxxx."
  }
}