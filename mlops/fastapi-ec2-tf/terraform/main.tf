# ── SSH key ──────────────────────────────────────────────
resource "tls_private_key" "fastapi" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "fastapi" {
  key_name   = "fastapi-key"
  public_key = tls_private_key.fastapi.public_key_openssh
}

resource "local_file" "private_key" {
  content         = tls_private_key.fastapi.private_key_pem
  filename        = "${path.module}/fastapi-key.pem"
  file_permission = "0400"
}

# ── Security Group ─────────────────────────────────────────
resource "aws_security_group" "fastapi" {
  name        = "fastapi-sg"
  description = "SSH + FastAPI"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP via NGINX"
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
    Name = "fastapi-sg"
  }
}

# ── EC2 ────────────────────────────────────────────────────
resource "aws_instance" "fastapi" {
  ami                    = var.ami
  instance_type          = var.instance_type
  key_name               = aws_key_pair.fastapi.key_name
  vpc_security_group_ids = [aws_security_group.fastapi.id]

  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = "fastapi-server"
  }
}
