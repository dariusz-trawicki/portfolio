resource "tls_private_key" "mlflow_key" {
  algorithm = "RSA"
  rsa_bits  = 4096 # More secure than the default 2048
}

# 2. AWS Key Pair – registers the public key in AWS
resource "aws_key_pair" "mlflow_key" {
  key_name   = var.key_name
  public_key = tls_private_key.mlflow_key.public_key_openssh

  tags = {
    Name = "MLflow Key Pair"
  }
}

# 3. Save the private key locally
resource "local_file" "private_key" {
  content         = tls_private_key.mlflow_key.private_key_pem
  filename        = "${path.module}/${var.key_name}.pem"
  file_permission = "0400" # Proper permissions applied automatically
}

# 4. (Optional) Save the public key as well
# resource "local_file" "public_key" {
#   content         = tls_private_key.mlflow_key.public_key_openssh
#   filename        = "${path.module}/${var.key_name}.pub"
#   file_permission = "0644"
# }
