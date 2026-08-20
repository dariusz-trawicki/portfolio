# Deploying AWS Resources (AWS VPC) with Terraform & GitHub Actions Automation

This project uses **Terraform** for infrastructure provisioning and **GitHub Actions** for automated deployment to AWS.

Terraform code provisions two `AWS EC2` instances (`WebServer1` and `WebServer2`) and automatically configures each with `Apache HTTP Server` to host a styled HTML page displaying the instance’s ID, type, and availability zone.

---

## 1. Repository Structure

```bash
.github/         # GitHub Actions workflows
terraform-vpc/   # Terraform configuration for AWS VPC, EC2 etc.
s3-backend       # Terraform configuration for AWS S3 bucket (for backend)
```

---

## 2. Deployment Workflow

The deployment process is automated through a `GitHub Actions workflow` located at: `.github/workflows/deploy.yml`.

Whenever changes are pushed to the `main` branch, this workflow will:

1. Initialize Terraform
2. Validate the configuration
3. Generate a Terraform plan
4. Apply infrastructure changes to AWS

---

### 3. Create S3 for backends

**NOTE** – `S3 Backend Bucket` required
Create the `S3 bucket` first — it’s required for storing the `Terraform state` file persistently. In `s3/backend/main.tf` file update the `s3 bucket name` (must be unique).

```bash
cd s3-backend
terraform init
terraform apply
cd ..
```

---

### 4. Create Github repo

Create Github public repo (e.g., name: `vpc-terraform-github-actions`).

#### Create Github secrets 

Open `https://github.com/ACCOUNT_NAME/vpc-terraform-github-actions/settings/secrets/actions`. Add secrets:
- `AWS_ACCESS_KEY` with apropriate value
- `AWS_SECRET_ACCESS_KEY` with apropriate value

---

### 5. Deployment Steps

#### Commit the code
Make sure both `.github` and `terraform-vpc` directories are included in your commit:

```bash
git add .
git commit -m "Deploy AWS resources"
git push origin main
```

**Note**: The `main branch` is configured to **trigger** the deployment workflow automatically.

---

### 6. Verifying the Deployment

Once the `GitHub Actions` job completes successfully:
- Open the `AWS Management Console`.
- Verify that the VPC and related AWS resources have been created as expected.

Open: `AWS > EC2 > Load balancers > application-load-balancer`
- Copy the `DNS name` (e.g. `application-load-balancer-1479085054.eu-central-1.elb.amazonaws.com`).
- Paste the copied `DNS name` into the browser’s address bar and open it. After opening the website through the `Load Balancer` and refreshing it several times, you can observe the `Load Balancer` distributing traffic between the EC2 instances.


---

### 7. Cleanup

7.1. In the `deploy.yml` file, uncomment the following code:

```yaml
      - name: Terraform Destroy
        id: destroy
        run: terraform destroy --auto-approve
        working-directory: ./terraform-vpc
```

Then push the changes to GitHub.

7.2. Destroy the S3 bucket

```bash
cd s3-backend
terraform init
terraform destroy
cd ..
```