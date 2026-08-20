# Run LLM Bielik on EC2

This Terraform configuration sets up an EC2 instance on AWS to run the Bielik large language model. It includes security group settings, key pair configuration, and user data script execution.

## Prerequisites
- An AWS account with appropriate permissions to create EC2 instances and security groups.
- Terraform installed on your local machine.
- An SSH key pair for accessing the EC2 instance.

## Usage
2. Navigate to the `terraformk` directory.
3. Update the `variables.tf` file with your specific values:
    - `public_key_path`: Path to your SSH public key.
    - `my_ip_cidr`: Your public IP address in CIDR notation

4. Run Terraform:

```bash
cd terraform
terraform init
terraform plan
terraform apply
# Output example:
# public_ip = "35.159.225.103"
```

5. Once the EC2 instance is running, you can SSH into it using the private key

```bash
ssh -i /path/to/your/private/key ubuntu@<EC2_INSTANCE_PUBLIC_IP>
```

6. Create needed files

- Create the files and put the code from files of `ec2_docker_serve_llm` folder:

```bash
ssh -i ~/.ssh/my_key.pem ubuntu@35.159.225.103 # example

vi serve.py # and put the code from ec2_docker_serve_llm/serve.py etc.
vi requirements.txt
vi Dockerfile
```

7. Use docker to run the LLM Bielik

```bash
# Add the user to the 'docker' group
sudo usermod -aG docker ubuntu

# Log out to apply group membership changes
exit

# Log in again
ssh -i ~/.ssh/my_key.pem ubuntu@35.159.225.103


# ------------------------------------------------------------
# Build the Docker image
# ------------------------------------------------------------
# This step may take several minutes depending on the system.
docker build . -t bielik_serve_openai


# ------------------------------------------------------------
# Run the container
# ------------------------------------------------------------
docker run -it -p 8000:8000 \
  -e LIT_SERVER_API_KEY=your_key \
  --gpus all bielik_serve_openai

# LIT_SERVER_API_KEY:
# - Defines the API key required to access the LitServer running inside the container.
# - This key must be provided by clients when querying the API.
# - The variable name is required and is expected by serve.py.
#
# Note:
# - This command runs the container in the foreground and blocks the terminal.
# - Use a second terminal to send requests to the API.


# ------------------------------------------------------------
# Test the running model (second terminal)
# ------------------------------------------------------------
ssh -i ~/.ssh/my_key.pem ubuntu@35.159.225.103

# Query the model using the OpenAI-compatible API endpoint.
# The API key must match the value of LIT_SERVER_API_KEY used when starting the container.
curl "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{
    "model": "lit",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant named Bielik. You answer only questions related to machine learning. If the question is not from the field of machine learning, you respond: \"I don't know.\" If the question is in a different language, you respond: \"Sorry, I only speak English.\""
      },
      {
        "role": "user",
        "content": "Who are you?"
      }
    ]
  }' | jq
```


8. Call the API from your local machine (public IP)

```bash
# On your local machine:

# Test 1: Basic request to verify connectivity and authentication
curl -i http://35.159.225.103:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"model":"lit","messages":[{"role":"user","content":"test"}],"max_tokens":20}'

# Test 2: Full chat-style request with a system prompt
curl "http://35.159.225.103:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{
    "model": "lit",
    "messages": [
{
  "role": "system",
  "content": "You are a helpful assistant named Bielik. You answer only questions related to machine learning. If the question is not from the field of machine learning, you respond: \"I don't know.\" If the question is in a different language, you respond: \"Sorry, I only speak English.\""
}
,
      {
        "role": "user",
        "content": "Who are you?"
      }
    ]
  }' | jq
```

Note: 
The value of X-API-Key must match the LIT_SERVER_API_KEY environment variable
used when starting the Docker container on the EC2 instance.

## Cleanup

To destroy all AWS resources created by Terraform (including the EC2 instance),
run:

```bash
terraform destroy
```

Confirm the destruction when prompted.
