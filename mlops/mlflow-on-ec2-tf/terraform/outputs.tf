output "ec2_public_dns" { value = aws_instance.mlflow.public_dns }
output "ec2_public_ip" { value = aws_instance.mlflow.public_ip }
# output "s3_bucket_name" { value = aws_s3_bucket.mlflow.bucket }
