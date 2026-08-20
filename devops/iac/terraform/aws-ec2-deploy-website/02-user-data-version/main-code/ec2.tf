resource "aws_instance" "web" {
  ami                    = var.ami_id
  instance_type          = "t3.micro"
  key_name               = aws_key_pair.ssh_key.key_name
  vpc_security_group_ids = [aws_security_group.website_proj_sg.id]
  availability_zone      = var.zone1

  tags = {
    Name    = var.instance_name
    Project = var.project_name
  }

  user_data = local.user_data

}

resource "aws_ec2_instance_state" "web-state" {
  instance_id = aws_instance.web.id
  state       = "running"
}
