# Terraform + Ansible over AWS SSM (Amazon Linux 2023 + Nginx)

This demo demonstrates running Ansible **entirely over AWS Systems Manager (SSM)** (no `SSH`), against an `EC2` on `Amazon Linux 2023`, installing a minimal web stack (`nginx`) and verifying it. It uses a **dynamic AWS inventory** and an **S3 bucket** for SSM file transport.


#### Project structure/tree

```text
.
├── README.md
├── ansible
│   ├── ansible.cfg
│   ├── group_vars
│   │   ├── all.yml
│   │   └── role__web.yml
│   ├── inventories
│   │   └── dev_aws_ec2.yml
│   ├── playbooks
│   │   └── site.yml
│   └── roles
│       ├── base
│       │   ├── tasks
│       │   │   └── main.yml
│       │   └── vars
│       │       └── main.yml
│       └── web
│           ├── defaults
│           │   └── main.yml
│           ├── handlers
│           │   └── main.yml
│           ├── tasks
│           │   └── main.yml
│           └── templates
│               └── nginx.conf.j2
└── terraform
    ├── envs
    │   └── dev
    │       ├── backend.tf
    │       ├── main.tf
    │       ├── outputs.tf
    │       └── variables.tf
    ├── modules
    │   ├── compute
    │   │   ├── main.tf
    │   │   ├── outputs.tf
    │   │   └── variables.tf
    │   └── network
    │       ├── main.tf
    │       ├── outputs.tf
    │       └── variables.tf
    └── s3-backend
        └── main.tf
```

---

### Goals

- Ansible control node in a Python virtualenv (pinned versions).
- Dynamic inventory from AWS (`amazon.aws.aws_ec2`).
- Connection over SSM (`amazon.aws.aws_ssm`) with uploads/downloads via S3.
- Minimal web role: install and start **nginx**.
- Options to view the site: SSM port-forward or public IP / ALB.

---

### Prerequisites

- AWS account + credentials configured locally (`aws configure`, or `AWS_PROFILE=...`).
- EC2 instance (Amazon Linux 2023) with:
  - **SSM Agent** (preinstalled on AL2023),
  - Instance profile allowing SSM (StartSession/SendCommand) and `S3` access for the chosen bucket,
  - Network egress to SSM endpoints (or VPC endpoints).
- **S3 bucket** in the same region as the instance, e.g. `tf-state-ansible-exp-123` (we use `eu-central-1` in examples).
- AWS CLI + **Session Manager Plugin** (on macOS: `brew install awscli session-manager-plugin`).
- macOS/Linux shell.


---

### Known-good tool versions

We pin these to avoid “works on my machine” issues:

```bash
cd ansible
# Python & virtualenv
pyenv install -s 3.12.8
pyenv shell 3.12.8
python -V  # => Python 3.12.8

python -m venv ~/.venvs/ans-ssm
source ~/.venvs/ans-ssm/bin/activate

# Python packages (Ansible + AWS SDK)
pip install --upgrade "pip==25.2"
pip install "ansible==10.*" "boto3==1.34.162" "botocore==1.34.162"

# Collections
ansible-galaxy collection install --force --upgrade amazon.aws community.aws
```

Check the **virtualenv’s** binaries (important if we also have Homebrew Ansible):

```bash
ansible --version
ansible-galaxy collection list | egrep 'amazon.aws|community.aws'
```

---

### Running it

#### IaC - terraform

Create **S3 bucket**:

```bash
cd ../terraform/s3-backend
terraform init
terraform apply -auto-approve
```

Create **EC2**:

```bash
cd ../envs/dev
terraform init
terraform apply -auto-approve
```

#### Activate the venv first

```bash
cd ../../../ansible
# source ~/.venvs/ans-ssm/bin/activate

ansible -i inventories/dev_aws_ec2.yml role__web \
  -m shell -a 'rpm -q nginx && ls -ld /etc/nginx || true'


ansible -i inventories/dev_aws_ec2.yml role__web \
  -b -m dnf -a 'name=nginx state=present'

ansible-playbook -i inventories/dev_aws_ec2.yml playbooks/site.yml
```

#### Quick SSM smoke tests:

```bash
# Ping (SSM)
ansible -i inventories/dev_aws_ec2.yml role__web -m ping

# Raw shell to prove SSM session works
ansible -i inventories/dev_aws_ec2.yml role__web   -m raw -a 'echo SSM_OK && uname -a' -vvv
```

#### Run the full play:

```bash
ansible-playbook -i inventories/dev_aws_ec2.yml playbooks/site.yml -vv
```

---

### Verifying nginx

Ad-hoc checks:

```bash
# Config test
ansible -i inventories/dev_aws_ec2.yml role__web -b -a "nginx -t"

# Service status
ansible -i inventories/dev_aws_ec2.yml role__web -b -a "systemctl status nginx --no-pager"

# HTTP response (on-instance)
ansible -i inventories/dev_aws_ec2.yml role__web   -a \
"curl -sI http://127.0.0.1:{{ nginx_port | default(80) }}"

ansible -i inventories/dev_aws_ec2.yml role__web \
-m debug -a 'var=public_ip_address'
# Output example:
# demo-web | SUCCESS => {
#     "public_ip_address": "3.79.113.107"
# }

ansible -i inventories/dev_aws_ec2.yml role__web \
  -m debug -a 'var=public_dns_name'
# Output example:
# demo-web | SUCCESS => {
#     "public_dns_name": "ec2-3-79-113-107.eu-central-1.compute.amazonaws.com"
# }
```

### View in your browser

Open: `http://3.79.113.107`

---

### Clean up

Terminate the EC2 instance.

```bash
cd ../terraform/envs/dev
terraform destroy
```

Delete S3 

```bash
cd ../../s3-backend

# S3 bucket cleanup (all versions & delete markers) 
B=tf-state-ansible-exp-123
R=eu-central-1

aws s3 rm "s3://$B" --recursive --region "$R" >/dev/null 2>&1 || true

while : ; do
  VERSIONS=$(aws s3api list-object-versions --bucket "$B" --region "$R" \
    --output text --query 'Versions[].[Key,VersionId]')
  MARKERS=$(aws s3api list-object-versions --bucket "$B" --region "$R" \
    --output text --query 'DeleteMarkers[].[Key,VersionId]')

  [ -z "$VERSIONS$MARKERS" ] && break

  if [ -n "$VERSIONS" ]; then
    echo "$VERSIONS" | while IFS=$'\t' read -r KEY VID; do
      [ -z "$KEY" ] && continue
      [ -z "$VID" ] && VID=null
      aws s3api delete-object --bucket "$B" --key "$KEY" --version-id "$VID" --region "$R"
    done
  fi

  if [ -n "$MARKERS" ]; then
    echo "$MARKERS" | while IFS=$'\t' read -r KEY VID; do
      [ -z "$KEY" ] && continue
      [ -z "$VID" ] && VID=null
      aws s3api delete-object --bucket "$B" --key "$KEY" --version-id "$VID" --region "$R"
    done
  fi
done

terraform destroy
```

