## End to End Machine Learning Project: CI/CD Pipeline with GitHub Actions and Terraform for AWS (OIDC + Terraform + Docker)

This project shows how to deploy a `Dockerized` application to an `EC2` instance using `GitHub Actions` and `Terraform` with `OIDC` authentication.

It includes:
- `Terraform` code to set up `AWS` resources (`EC2`, `ECR`, `IAM roles`).
- `GitHub Actions` workflow to `terraform apply`, build and push `Docker` images to `ECR` and deploy to `EC2` instance configured to run `Docker` and pull images from `ECR`.

#### Problem statement

This project understands how the student's performance (test scores) is affected by other variables such as Gender, Ethnicity, Parental level of education, Lunch and Test preparation course.

The code and project details are available in the repository:
https://github.com/dariusz-trawicki/ml-cicd-project