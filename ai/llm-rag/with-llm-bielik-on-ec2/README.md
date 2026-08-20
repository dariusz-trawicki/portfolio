# Create Chatbot QA (RAG) with LLM BIELIK

## RAG Architecture and Components

The `RAG` (Retrieval-Augmented Generation) setup consists of the following components:

- **LLM**: `Bielik`. A large language model trained on Polish-language data, deployed on an EC2 instance in AWS.

- **text-embeddings-inference**. An `API server` providing access to the embedding model. Implemented as a lightweight HTTP service (based on `FastAPI`).

- **Embedding model**: `silver-retriever-base-v1` (Hugging Face). Runs locally in a Docker container.

- **Vector database**: Weaviate. Runs locally in Docker and stores document embeddings.


### Execution Flow

1. `run_embedding_model.sh`
Starts a Docker container with the embedding model locally.

2. `run_vector_db.sh`
Starts the Weaviate vector database in a Docker container locally.

3. **Data ingestion**
Sample data located in the `example_data` directory is:
- split into chunks,
- converted into embeddings,
- and stored in the `vector database` (using the ingestion script: `ingest_data.py`).

4. **RAG querying**
The `LLM` is queried using the `Retrieval-Augmented Generation` approach in the script:
`rag.py`, which retrieves relevant context from `Weaviate` and injects it into the prompt sent to Bielik.


### Notes
The embedding and vector database components run locally, while the LLM runs remotely on AWS EC2.
Communication between components is handled over HTTP APIs, enabling a fully decoupled RAG pipeline.


## 1. PART: Run LLM Bielik on EC2

This `Terraform` configuration sets up an `EC2 instance` on `AWS` to run the `Bielik large language model`. It includes security group settings, key pair configuration, and user data script execution.

### Prerequisites
- An `AWS account` with appropriate permissions to create `EC2 instances` and `security groups`.
- `Terraform` installed on your local machine.
- An `SSH key pair` for accessing the EC2 instance.

### Usage
1. Navigate to the `terraform` directory.
2. Update the `variables.tf` file with your specific values:
    - `public_key_path`: Path to your SSH public key.
    - `my_ip_cidr`: Your public IP address in CIDR notation

3. Run Terraform:

```bash
cd terraform
terraform init
terraform plan
terraform apply
# Output example:
# public_ip = "35.159.225.103"
```

4. Once the EC2 instance is running, you can SSH into it using the private key

```bash
ssh -i /path/to/your/private/key ubuntu@<EC2_INSTANCE_PUBLIC_IP>
```

5. Create needed files

- Create the files and put the code from files of `ec2_docker_serve_llm` folder:

```bash
ssh -i ~/.ssh/mykey ubuntu@35.159.106.157 # example

vi serve.py # and put the code from ec2_docker_serve_llm/serve.py etc.
vi requirements.txt
vi Dockerfile
```

6. Use docker to run the `LLM Bielik`

```bash
# Add the user to the 'docker' group
sudo usermod -aG docker ubuntu

# Log out to apply group membership changes
exit

# Log in again
ssh -i ~/.ssh/my_key.pem ubuntu@35.159.106.157


# ------------------------------------------------------------
# Build the Docker image
# ------------------------------------------------------------
# This step may take several minutes depending on the system.
docker build . -t bielik_serve


# ------------------------------------------------------------
# Run the container
# ------------------------------------------------------------
docker run -it -p 8000:8000 \
  -e LIT_SERVER_API_KEY=your_key \
  --gpus all bielik_serve

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
ssh -i ~/.ssh/my_key.pem ubuntu@35.159.106.157

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


7. Call the API from your local machine (public IP)

```bash
# On your local machine:

# Test 1: Basic request to verify connectivity and authentication
curl -i http://35.159.106.157:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"model":"lit","messages":[{"role":"user","content":"test"}],"max_tokens":20}'

# Test 2: Full chat-style request with a system prompt
curl "http://35.159.106.157:8000/v1/chat/completions" \
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


---

## 2. PART: Run: Vector DB and embedding model + ingest DATA into DB

1. Run embedding model

```bash
./run_embedding_model.sh

# ------------------------------------------------------------
# Test the running embedding model (second terminal)
# ------------------------------------------------------------
curl 127.0.0.1:8080/embed \
    -X POST \
    -d '{"inputs":"What is Deep Learning?"}' \
    -H 'Content-Type: application/json'
```

2. Run Weaviate vector DB

```bash
# in "run_vector_db.sh" set the port (example: 8081)
./run_vector_db.sh
```

3. Ingest data into Weaviate DB

Script `ingest_data.py` ingest example data from `example_data` folder into `Weaviate` DB.

```bash
uv sync
uv run python ingest_data.py
```

 
## 3. PART. RAG

In `rag.py`, set the current values for `BASE_URL` and `LIT_SERVER_API_KEY`.

```bash
uv run python rag.py
```


## Cleanup

To destroy all AWS resources created by Terraform (including the EC2 instance),
run:

```bash
terraform destroy
```

Confirm the destruction when prompted.
