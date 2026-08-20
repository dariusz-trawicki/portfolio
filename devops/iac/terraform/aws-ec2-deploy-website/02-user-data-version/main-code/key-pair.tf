resource "aws_key_pair" "ssh_key" {
  key_name   = var.aws_key_pair_name
  public_key = file("${var.private_key_path}.pub")
}
