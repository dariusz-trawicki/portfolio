# Deploying EKS Cluster Using Terraform, Jenkins, and GitHub — with NGINX Deployment on Kubernetes

```text
+----------------------+
| 1. Jenkins (on EC2)  |
| - Jenkinsfile        |
| - AWS credentials    |
+----------+-----------+
           |
           v
+-----------------------------+
| 2. Checkout from GitHub     |
| - Branch: main              |
| - Repo: terraform-jenkins… |
+-------------+---------------+
              |
              v
+----------------------------+
| 3. Initialize Terraform    |
| - terraform init           |
| - AWS credentials injected |
+-------------+--------------+
              |
              v
+---------------------------+
| 4. Format & Validate      |
| - terraform fmt           |
| - terraform validate      |
+-------------+-------------+
              |
              v
+-----------------------------+
| 5. Plan Infrastructure      |
| - terraform plan            |
| - Jenkins input confirmation|
+-------------+---------------+
              |
              v
+--------------------------------+
| 6. Apply or Destroy via        |
| - terraform $action            |
|   (apply/destroy)              |
+---------------+----------------+
                |
                v
+----------------------------------+
| 7. Configure EKS access          |
| - update-kubeconfig              |
| - create-access-entry (optional)|
| - associate-access-policy       |
+---------------+-----------------+
                |
                v
+-----------------------------------+
| 8. Deploy NGINX to EKS Cluster    |
| - kubectl apply deployment.yaml   |
| - kubectl apply service.yaml      |
+-----------------------------------+
```

Plan:
1. Create S3 for backends.
2. Create EC2 instance with Jenkins.
3. Create Github repo and push the `EKS tf code` to the Github.
4. Run Jenkins pipeline for creating EKS cluster. 
6. Implement a deployment file -> kubectl -> deploy nginx on EKS cluster -> accessing to app via LB


### Create S3 for backends

**NOTE** – `S3 Backend Bucket` required
Create the `S3 bucket` first — it’s required for storing the `Terraform state` file persistently. In `s3/backend/main.tf` file update the `s3 bucket name` (unique).

```bash
cd s3-backend
terraform init
terraform apply
cd ..
```

### Create EC2 instance with Jenkins

```bash
cd jenkins-server
# In backend.tf file update the s3 bucket name

# Create AWS Key Pair (for connction to EC2 via `ssh`)
aws ec2 create-key-pair \
  --key-name jenkins-server-key \
  --query 'KeyMaterial' \
  --output text > jenkins-server-key.pem
chmod 400 jenkins-server-key.pem
# Test
aws ec2 describe-key-pairs --key-names jenkins-server-key
# OR: in the AWS console visit: EC2 > Key pairs

terraform init
terraform plan
terraform apply
cd ..
```

#### NOTE:
`jenkins-install.sh` –> a script that automatically runs on the created `EC2` instance and installs:
- `Jenkins`
- `Git`
- `Terraform`
- `kubectl`
- `AWS CLI`


### Public IPv4 address of EC2

Visit: `AWS > EC2 -> check YOUR_EC2` -> copy `Public IPv4 address`
(e.g. `3.125.17.150`)

OR locally via AWS CLI:

```bash
# Read public IPv4 address of EC2 via aws:
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=Jenkins-Server" \
            "Name=instance-state-name,Values=running" \
  --query "Reservations[*].Instances[*].PublicIpAddress" \
  --output text
# *** output (example) ***
# 3.125.17.150
```

### Open the Jenkins UI

Visit: http://3.125.17.150:8080/

Open: EC2 > Instances > check YOUR_EC2 -> CONNECT and run:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
# *** output (example) ***
# e7314b26f5c9434e844f8b31392da570
```

#### Connect to EC2 via `ssh`

```bash
# connect to EC2:
ssh -i jenkins-server-key.pem ec2-user@3.125.17.150
# *** output (example) ***
# [ec2-user@ip-10-0-1-94 ~]$

# Get the "initial pass":
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
# *** output (example) ***
# e7314b26f5c9434e844f8b31392da570
```

### Initial Jenkis

Open: http://3.125.17.150:8080/, login with `initial pass`, choose `install plugins` option and create admin user.


### Github - create repo

 **NOTE:**  
- Make sure to update the **S3 bucket** name in the `eks/backend.tf` file  
- and the **EKS cluster** name in the `eks/locals.tf` file to match the setup.

Create public repo (e.g., name: `terraform-jenkins-eks`) on Github and `push` the code (`eks` folder) to the Github (into `main` branch).


### Jenkins UI - create new project
On http://3.125.17.150:8080/ and create new project:
- Name e.g.: `terraform-eks-cicd`
- Select an item type: `Pipeline`
- Add `access keys` and `secret access keys`:
  - open/click `Manage Jenkins` (top-right button) > Credentials > click on `global`
    - click `Add credentials` and:
      - choose Kind: `Secret text`, 
      - set:
          - secret: `AKIBJ2XXXXXXXXXX` - my AWS ACCESS KEY ID value
          - as ID: `AWS_ACCESS_KEY_ID`
      - click `Create`
    - click `Add credentials` and:
      - choose Kind: `Secret text`, 
      - set:
          - secret: `aoKjxxxxxxxxxx` - my AWS SECRET ACCESS KEY value
          - as ID: `AWS_SECRET_ACCESS_KEY`
      - click `Create`

#### Jenkins pipeline code

Open: `Jenkins > terraform-eks-cicd > Configure` -> `Pipeline` section and put the code into `Script` field (replace `ACCOUNT_NAME` with your `GitHub username`):

```text
pipeline {
    agent any

    environment {
        AWS_ACCESS_KEY_ID     = credentials('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = credentials('AWS_SECRET_ACCESS_KEY')
        AWS_DEFAULT_REGION = "eu-central-1"
    }

    stages {
        stage('Checkout SCM') {
            steps {
                script {
                    checkout scmGit(branches: [[name: '*/main']], extensions: [], userRemoteConfigs: [[url: 'https://github.com/ACCOUNT_NAME/terraform-jenkins-eks.git']])
                }
            }
        }
    }
}
```

...and click: `SAVE`.

#### RUN the test pipeline (only checkout part)
Visit:`Jenkins > terraform-eks-cicd` click `Build Now`


### RUN the entire pipeline (create EKS cluster)

#### Add parameter `action`

Visit: `Jenkins > terraform-eks-cicd > Configuration`
Go to: `This project is parameterized?` and check it, click `Add Parameter` choose `Choice Parametr` and set:
- Name: `action`
- Choises:

```text
apply
destroy
```

- Description e.g.: `Action to be performed by Terraform`


#### Jenkins - the full pipeline code

NOTE: In `Jenkinsfile` file code:
1. Replace: `AWS_ACCOUNT_NUMBER` and `USER_ID` with the actual values.
2. The EKS `cluster name` **must be the same** in both:
- in the `eks/locals.tf` file: 
  `name   = "eks-example-cluster"`
- and in the Jenkins pipeline code (in the `Jenkinsfile`, in these lines):
  - `aws eks update-kubeconfig --name eks-example-cluster`
  - `--cluster-name eks-example-cluster`  (2 lines)

Put the code from `Jenkinsfile` file into:
`Jenkins > terraform-eks-cicd > Configuration` (into `Script` field) and click
`SAVE`.

### RUN the pipeline:
`Jenkins > terraform-eks-cicd` click `Build with parameters` 
and choose `apply`


### Load Balancer - Nginx

Visit: `AWS > EC2 > Load Balancers`, copy the `DNS name` of the created `LB`
e.g.:
- LB name: `accedd053b52d41d48e81a218e22e8f3`
- LB DNS: `http://accedd053b52d41d48e81a218e22e8f3-373051670.eu-central-1.elb.amazonaws.com/`

Open that DNS address in your browser. You should see the `"Welcome to nginx!"` page.

### Cleanup

`Jenkins > terraform-eks-cicd` click `Build with parameters` 
and choose e.g. `destroy`.

```bash
cd jenkins-server
terraform destroy
cd ..
cd s3-backend
terraform destroy
```
