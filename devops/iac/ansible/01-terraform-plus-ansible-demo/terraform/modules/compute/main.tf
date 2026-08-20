data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_security_group" "web" {
  name        = "${var.name}-web-sg"
  description = "Web ingress"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name}-web-sg"
  }
}

# EC2 z SSM (bez SSH! będziemy używać Ansible przez SSM)
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name

  tags = {
    Name    = "${var.name}-web"
    Role    = "web"
    Env     = var.env
    Ansible = "managed"
  }

  # modules/compute/main.tf (w zasobie aws_instance "web")
  user_data = <<-EOT
#!/bin/bash
set -euxo pipefail
# Amazon Linux 2023: zapewnij, że agent SSM jest zainstalowany i działa
dnf -y install amazon-ssm-agent || true
systemctl enable --now amazon-ssm-agent
EOT

}

# Uprawnienia do SSM (Session Manager/Run Command)
resource "aws_iam_role" "ssm_role" {
  name = "${var.name}-ssm-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm_profile" {
  name = "${var.name}-ssm-profile"
  role = aws_iam_role.ssm_role.name
}
