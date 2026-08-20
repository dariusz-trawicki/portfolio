# PLLuM on AWS VM

Running the Polish language model [PLLuM](https://huggingface.co/CYFRAGOVPL/Llama-PLLuM-8B-chat) on a GPU-backed AWS EC2 instance.

## Stack

- **Terraform** — provisions EC2 `g4dn.xlarge` (Tesla T4, CUDA 12.2)
- **NVIDIA Driver 535** — GPU support on the VM
- **NVIDIA Container Toolkit** — exposes GPU to Docker
- **mistral.rs** (Docker) — serves PLLuM via OpenAI-compatible `/v1` API
- **SSH tunnel** — local access at `localhost:8080`
- **Python AsyncOpenAI** — client for querying the model

---

## 1. Provision the VM

```bash
cd ./terraform
mkdir ssh
ssh-keygen -t rsa -b 4096 -C "email@example.com" -f ./ssh/id_rsa

terraform init
terraform plan
terraform apply
```

---

## 2. Connect via SSH

```bash
PUBLIC_IP=$(aws ec2 describe-instances \
  --query "Reservations[*].Instances[*].PublicIpAddress" \
  --output text --region eu-central-1)

ssh -i ./ssh/id_rsa -Y ubuntu@$PUBLIC_IP
```

---

## 3. Set Up the VM

### NVIDIA Driver

```bash
sudo apt update && sudo apt upgrade
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt-get install nvidia-driver-535
sudo reboot  # SSH session will drop
```

Reconnect after reboot and verify:

```bash
ssh -i ./ssh/id_rsa -Y ubuntu@$PUBLIC_IP
nvidia-smi
```

### Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

### NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

GPU - benchmark

```bash
docker run --gpus all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark
```

---

## 4. Run PLLuM-8B

```bash
COMPUTE_CAPABILITIES=75
VERSION_SHA=f1a56f6

docker run -it --rm --name pllum -p 8080:80 --gpus all \
	-v $HOME/.cache/huggingface:/root/.cache/huggingface \
	ghcr.io/ericlbuehler/mistral.rs:cuda-$COMPUTE_CAPABILITIES-sha-$VERSION_SHA \
	plain \
	--model-id CYFRAGOVPL/Llama-PLLuM-8B-chat
```

---

## 5. Open SSH Tunnel

In a **second terminal** on your local machine:

```bash
PUBLIC_IP=$(aws ec2 describe-instances \
  --query "Reservations[*].Instances[*].PublicIpAddress" \
  --output text --region eu-central-1)

ssh ubuntu@$PUBLIC_IP -i ./ssh/id_rsa -L 8080:localhost:8080 -TN /bin/false
```

---

## 6. Test the API

In a **third terminal** on your local machine:

```bash
# Health check
curl http://localhost:8080/
# OK

# List models
curl http://localhost:8080/v1/models
# {"object":"list","data":[{"id":"CYFRAGOVPL/Llama-PLLuM-8B-chat",...}]}

# Chat completion
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral",
    "messages": [
      {"role": "user", "content": "Witaj świecie!"}
    ]
  }'
# {"choices":[{"message":{"content":"Dzień dobry! W czym mogę pomóc?",...}}],...}
```

### Python Client

```bash
cd ./src
python3 -m venv venv
source venv/bin/activate
pip install openai

python test_pllum.py
# Output example:
# Dzień dobry! W czym mogę Ci pomóc?
```

---

## 7. Cleanup

```bash
terraform destroy
```
