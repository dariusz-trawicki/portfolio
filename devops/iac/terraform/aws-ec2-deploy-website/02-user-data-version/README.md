# Terraform: Automated Website Deployment on AWS EC2 (Apache + Tooplate)

**Variant 02** — `Cloud-Init` (`user_data`): All bootstrap steps run on first boot via `EC2` user data.

#### Step1. Generate key pair (for ssh connection)

```bash
cd main-code
ssh-keygen -t ed25519 -f ./test-key -C "Test key for ec2"
chmod 400 ./test-key
```

#### Step2. Create S3 for backend (remote terraform state)

In `s3-backend/main.tf` file set the unique bucket name.

```bash
cd ../s3-backend
terraform init
terraform apply
```


#### Step3. Initialize parameters - terraform variables


In `main-code/terraform.tfvars` set:

```hcl
region            = "eu-central-1"
zone1             = "eu-central-1a"
aws_key_pair_name = "web-server-key"
private_key_path  = "./test-key"
instance_name     = "web-server"
sg_name           = "website-proj-sg"
project_name      = "WebsiteProject"
ssh_user          = "ubuntu"
ami_id            = "ami-0a116fa7c861dd5f9" # Ubuntu 22.04 LTS in eu-central-1
```

**NOTE**: `private_key_path` should point to the locally generated `private SSH key` (e.g., `~/.ssh/test-key`; here: `./test-key`). The corresponding `public key` must use the same basename with the `.pub` suffix (e.g., `~/.ssh/test-key.pub`).

#### Step4. Deploy EC2 with website

```bash
cd ../main-code
terraform init
terraform validate
terraform plan
terraform apply
# Example outputs:
# WebPrivateIP = "172.31.44.225"
# WebPublicIP = "52.210.51.41"
```

#### Verify SSH (optional)

```bash
# If needed (if host key changed):
# ssh-keygen -R 52.210.51.41
ssh -i ./test-key ubuntu@52.210.51.41
cd /
ls -l
cd var/www/html
ls
# *** output ***
# css  fontawesome-5.5  img  index.html  js  magnific-popup  slick
```

#### Step5. Access the website

In the browser open: http://52.210.51.41

#### Step6. Cleanup

```bash
cd main-code
terraform destroy

cd ../s3-backend
terraform destroy
```