# GitOps Project: CI/CD with Github actions

### Overview

**GitHub Actions** runs two workflows:
1. **Terraform Workflow** – provisions AWS infrastructure (`EKS`, `VPC`).
2. **Build, Test & Deploy** – builds the app, pushes the Docker image to `ECR`, and deploys to `EKS` with `Helm`.

The project is split into two repositories:

- **Infrastructure as Code** (IaC) — Terraform for `VPC/EKS/ECR`:
  - [`iac-vprofile-eks`](https://github.com/dariusz-trawicki/iac-vprofile-eks)
- **Application CI/CD** — **GitHub Actions** to build, test, push to `ECR`, and deploy to `EKS` with `Helm`:
  - [`vprofile-actions`](https://github.com/dariusz-trawicki/vprofile-actions)


#### Step 1. Terraform workflow (IaC)

**AWS resources**: the workflow manages an **Amazon EKS** cluster inside a **VPC subnet**.

#### Step 2. Build, test & deploy (application)

- The `workflow` fetches application code.
- **Build & test** with **Maven**.
- **Containerize** with **Docker** and push the image to **Amazon ECR**.
- **Deploy** to the `EKS cluster` using **Helm charts** (install/upgrade).

### Result

- Infra changes are validated and applied.
- Every successful build produces a versioned image in `ECR` and updates the running workload on `EKS` via `Helm`.
- The stack runs in AWS (`EKS` + `ECR` in a `VPC`), orchestrated entirely from `GitHub Actions`.

## Run (main steps)

### Terraform workflow (IaC)

Take the code from: [`iac-vprofile-eks`](https://github.com/dariusz-trawicki/iac-vprofile-eks) repository.

#### Create AWS resources: S3 bucket and ECR

```bash
cd iac-vprofile-eks/s3-backend
terraform init
terraform validate
terraform plan
terraform apply

cd ../ecr
terraform init
terraform validate
terraform plan
terraform apply
# ***output (example) ***
# ecr_repo_url = "2534xxxxxxx07.dkr.ecr.eu-central-1.amazonaws.com/vprofileapp"
```

### Create Github Secrets

#### AWS accesss: Create AWS `new user`:

In AWS console: `IAM > Users > Create user`: Name: `gitops`
- Click `Next` and choose: `Attach policies directly`, select:
  - `AdministaratorAccess` # for test only
- Click `Next` and `Create user`.
- Click `gitops` user (link), choose: `Security credentials`, 
- Click: `Create access key`, choose: `Command Line Interface (CLI)` + check:
`I understand the above recommendation and want to proceed to create an access key.` 
- Click: `Create accesss key` and COPY values:
  - Access key: AKIATWBJXXXXXXXXXXXXXX
  - Secret access key: kIYerj+q7jbxxxxxxxxxxxxxxx

#### Create the secrets:

Go to the repositories ([`iac-vprofile-eks`](https://github.com/dariusz-trawicki/iac-vprofile-eks) and [`vprofile-actions`](https://github.com/dariusz-trawicki/vprofile-actions)) on `GitHub` and:
- Click on the `Settings` tab.
- Click on `Secrets and variables > Actions`.
- Click the `New repository secret` button.

Add the following secrets:
- Name: AWS_ACCESS_KEY_ID
- Value: AKIATWBJXXXXXXXXXXXXXX
- Name: AWS_SECRET_ACCESS_KEY
- Value: kIYerj+q7jbxxxxxxxxxxxxxxx

Click `Add secret` to save each secret.

#### Create secret for state backend bucket name (in [`iac-vprofile-eks`](https://github.com/dariusz-trawicki/iac-vprofile-eks) repo)

**NOTE**: The name of bucket is defined in `iac-vprofile-eks/s3-backend/main.tf` file.

Create secret:
- Name: BUCKET_TF_STATE
- Value: vprofile-eks-state-12345

#### Create secret for ECR URL

**NOTE**: Terraform returned the ECR repository URL.

```bash
ecr_repo_url = "2534xxxxxxx07.dkr.ecr.eu-central-1.amazonaws.com/vprofileapp"
```

**NOTE**: Copy only: `2534xxxxxxx07.dkr.ecr.eu-central-1.amazonaws.com`


In [`vprofile-actions`](https://github.com/dariusz-trawicki/vprofile-actions) repository, create new secret:
- Name: REGISTRY
- Value: 2534xxxxxxx07.dkr.ecr.eu-central-1.amazonaws.com


#### Create EKS cluster with GitHub action

In the [`iac-vprofile-eks`](https://github.com/dariusz-trawicki/iac-vprofile-eks) repository, run the `Vprofile IAC` action.


### CI/CD with Github actions

- **CI**: **Build** and **push** image to **ECR**
- **CD**: **Deploy** to **EKS**

In [`vprofile-actions`](https://github.com/dariusz-trawicki/vprofile-actions/actions) repository run `vprofile actions` action. The `GitHub Actions` workflow runs the app tests, builds a `Docker image`, pushes it to `Amazon ECR` and deploy to **EKS**.

### Cleanup

#### 1. Remove ingress controller

In `IAM > Users` choose `gitops` create new `access key`.
- Access key: XXXXXXXXXXXXXXXX
- Secret access key: r5mmbxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

```bash
aws configure
aws eks update-kubeconfig --region eu-central-1 --name vprofile-eks
# check:
kubectl get nodes

kubectl delete -n ingress-nginx -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/cloud/deploy.yaml
```

#### 2. Remove Helm release, EKS, ECR and S3 bucket

```bash
cd vprofile-actions
helm list
helm uninstall vprofile-stack  # see main.yml

cd ../iac-vprofile-eks/terraform
terraform init
terraform destroy

cd ../ecr
terraform init
terraform destroy

cd ../s3-backend
terraform init
terraform destroy
```
