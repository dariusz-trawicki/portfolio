# AI / Machine Learning

LLM systems, computer vision, generative models, and predictive modeling —
from experiments to models running in the cloud.

## Categories

| Category | Focus |
|---|---|
| [llm-rag](llm-rag/) | Retrieval-augmented generation: semantic search, vector stores, agentic retrieval |
| [llm-agents](llm-agents/) | Function calling, tool use, voice and multi-step agent workflows |
| [llm-deployment](llm-deployment/) | Serving LLMs — managed APIs, serverless, self-hosted GPU instances |
| [llm-fine-tuning](fine-tuning/) | Adapting open models to domain-specific tasks |
| [llm-tooling](llm-tooling/) | Applied LLM utilities and skill-chain workflows |
| [computer-vision](computer-vision/) | Classification, detection, tracking, pose estimation, OCR |
| [gen-ai](gen-ai/) | Generative image models |
| [predictive-modeling-optimization](predictive-modeling-optimization/) | Classical ML pipelines and mathematical optimization |

## Highlights

### LLM & RAG

| Project | Description | Stack |
|---|---|---|
| [llm-rag/ai-agentic](llm-rag/ai-agentic/) | Agentic RAG — retrieval driven by a tool-using agent rather than a fixed pipeline | LangChain, vector store, Python |
| [llm-rag/with-nvidia](llm-rag/with-nvidia/) | RAG built on NVIDIA inference stack | NVIDIA NIM, Python |
| [llm-rag/gcp-vertex-ai](llm-rag/gcp-vertex-ai/) | Managed RAG on Google Cloud | Vertex AI, GCP |
| [llm-rag/vectorless-pageindex](llm-rag/vectorless-pageindex/) | Retrieval without a vector database — page-level indexing approach | Python, LLM API |
| [llm-rag/local-langchain-huggingface](llm-rag/local-langchain-huggingface/) | Fully local RAG, no external API calls | LangChain, HuggingFace, FAISS |

### Agents

| Project | Description | Stack |
|---|---|---|
| [llm-agents/agent-pydanticai-function-calling](llm-agents/agent-pydanticai-function-calling/) | Type-safe function calling with structured outputs | PydanticAI, Python |
| [llm-agents/langgraf-openai-tavily](llm-agents/langgraf-openai-tavily/) | Graph-based agent with web search as a tool | LangGraph, OpenAI, Tavily |
| [llm-agents/realtime-groq-gpt-voice-chat](llm-agents/realtime-groq-gpt-voice-chat/) | Low-latency voice conversation | Groq, OpenAI, streaming audio |

### Deployment & fine-tuning

| Project | Description | Stack |
|---|---|---|
| [llm-deployment/pllum-on-aws-ec2](llm-deployment/pllum-on-aws-ec2/) | Self-hosted Polish LLM on GPU instances, provisioned as code | HuggingFace, EC2, Terraform |
| [llm-deployment/aws-lambda-bedrock-tf](llm-deployment/aws-lambda-bedrock-tf/) | Serverless GenAI endpoint, pay-per-request | Bedrock, Lambda, Terraform |
| [llm-deployment/azure-openai](llm-deployment/azure-openai/) | LLM integration on Azure, with and without IaC | Azure OpenAI, Terraform |
| [fine-tuning/pllum-kaggle-pl](fine-tuning/pllum-kaggle-pl/) | Fine-tuning a Polish open model for a domain task | PyTorch, HuggingFace, PEFT |
| [fine-tuning/news-class](fine-tuning/news-class/) | Fine-tuned classifier for news categorization | Transformers, PyTorch |
