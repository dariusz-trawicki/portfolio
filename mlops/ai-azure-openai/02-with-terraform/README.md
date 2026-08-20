# Azure OpenAI with Terraform

Minimal example of Azure OpenAI API integration using Python and `uv`.
Infrastructure provisioned with **Terraform**.

---

## Azure Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed
- [Terraform](https://developer.hashicorp.com/terraform/install) installed
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- Azure account with a paid subscription (Pay-As-You-Go or higher)

### 1. Login to Azure

```bash
az login
```

### 2. Provision Infrastructure with Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This will create:
- Resource Group
- Azure OpenAI resource
- Model deployment (`gpt-4o-mini`)

### 3. Get credentials from Terraform outputs

```bash
terraform output endpoint
terraform output -raw primary_key
terraform output deployment_name
```

---

## Project Setup

### 1. Initialize Python project

```bash
uv init
uv add openai python-dotenv
```

### 2. Create `.env` file

```env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_KEY=your_primary_key
AZURE_DEPLOYMENT_NAME=gpt-4-mini
```

Use values from `terraform output` above.

---

## Examples

### 1. chat_basic.py

Minimal example of a single-turn chat completion with Azure OpenAI.

Sends one question to the model and prints the response.
No conversation history — each call is independent.

#### Run

```bash
uv run chat_basic.py
```

**Example output:**
```
The average distance from the Earth to the Moon is about 384,400 kilometers (238,855 miles).
This distance can vary slightly due to the Moon's elliptical orbit around the Earth.
```

---

### 2. chat_multiturn.py

Demonstrates **multi-turn conversation** — passing the full message history to the API.

Unlike a single prompt, multi-turn sends the entire conversation context:
- `system` — sets the assistant's behavior
- `user` — user message
- `assistant` — previous assistant response (injected manually)
- `user` — follow-up question

This is how chatbots maintain context — the model has no memory between calls,
so the full history must be passed on every request.

Also demonstrates additional parameters:
- `max_completion_tokens` — hard limit on response length
- `temperature`, `top_p` — control response randomness
- `frequency_penalty`, `presence_penalty` — reduce repetition

#### Run

```bash
uv run chat_multiturn.py
```

**Example output:**
```
1. Iconic Symbol: It is one of the most recognizable landmarks in the world and a symbol of Paris and France.
2. Engineering Marvel: When it was completed...
```

---

## Cleanup

To remove all Azure resources:

```bash
cd terraform
terraform destroy
```
