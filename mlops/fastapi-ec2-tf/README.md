# FastAPI on AWS EC2 with Terraform

A FastAPI application deployed to AWS EC2 using Terraform. Includes NGINX as a reverse proxy and systemd for process management.

## Architecture

```
Internet → port 80 → NGINX → 127.0.0.1:8000 → Uvicorn → FastAPI
```

## Stack

- **FastAPI** — Python web framework
- **Uvicorn** — ASGI server
- **NGINX** — reverse proxy
- **systemd** — process manager (auto-restart on crash)
- **Terraform** — infrastructure as code (EC2, Security Group, SSH Key)

## Project Structure

```
├── README.md
└── terraform/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── user_data.sh 
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/items` | Create item |
| `GET` | `/items` | List items (optional `?limit=10`) |
| `GET` | `/items/{item_id}` | Get item by index |

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- AWS CLI configured (`aws configure`)
- AWS account with EC2 permissions

## Deploy

```bash
terraform init
terraform apply
```

Terraform will automatically:
- Generate an SSH key pair
- Save the private key as `fastapi-key.pem`
- Provision EC2 with Ubuntu 22.04
- Install Python, FastAPI, Uvicorn, NGINX
- Configure systemd service for auto-restart
- Configure NGINX as reverse proxy on port 80

## Outputs

```
public_ip   = "1.2.3.4"
api_url     = "http://1.2.3.4"
docs_url    = "http://1.2.3.4/docs"
ssh_command = "ssh -i fastapi-key.pem ubuntu@1.2.3.4"
```

> **Note:** Wait ~60 seconds after `apply` for `user_data.sh` to finish executing.

## Usage

```bash
# Health check
curl http://<PUBLIC_IP>/

# Create item
curl -X POST 'http://<PUBLIC_IP>/items' \
     -H "Content-Type: application/json" \
     -d '{"text": "apple"}'

# List items
curl 'http://<PUBLIC_IP>/items?limit=3'

# Get item by index
curl 'http://<PUBLIC_IP>/items/0'

# 404 example
curl 'http://<PUBLIC_IP>/items/999'
```

## Interactive Docs

FastAPI generates documentation automatically:

```
http://<PUBLIC_IP>/docs    # Swagger UI
http://<PUBLIC_IP>/redoc   # ReDoc
```

## SSH Access

```bash
ssh -i fastapi-key.pem ubuntu@<PUBLIC_IP>

# Check service status
systemctl status fastapi

# Live logs
journalctl -u fastapi -f

# Check NGINX
systemctl status nginx
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `region` | `eu-central-1` | AWS region |
| `ami` | Ubuntu 22.04 LTS | EC2 AMI |
| `instance_type` | `t2.micro` | EC2 instance type |

## Cleanup

```bash
terraform destroy
```
