# AWS: EKS Cluster example

## RUN

- Terraform:

```bash
cd terraform
terraform init
terraform apply
```

- Config `kubectl`:

```bash
aws eks --region eu-central-1 update-kubeconfig --name demo
```
