# AI / Machine Learning

LLM systems, computer vision, generative models, and predictive modeling —
from experiments to models running in the cloud.

## Categories

| Category | Focus |
|---|---|
| [llm-rag](llm-rag/) | Retrieval-augmented generation: semantic search, vector stores, agentic retrieval |
| [llm-agents](llm-agents/) | Function calling, tool use, voice and multi-step agent workflows |
| [llm-deployment](llm-deployment/) | Serving LLMs — managed APIs, serverless, self-hosted GPU instances |
| [fine-tuning](fine-tuning/) | Adapting open models to domain-specific tasks |
| [llm-tooling](llm-tooling/) | Applied LLM utilities and Claude Code skill-chain workflows |
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
| [llm-agents/langgraph-openai-tavily](llm-agents/langgraph-openai-tavily/) | Graph-based agent with web search as a tool | LangGraph, OpenAI, Tavily |
| [llm-agents/realtime-groq-gpt-voice-chat](llm-agents/realtime-groq-gpt-voice-chat/) | Low-latency voice conversation | Groq, OpenAI, streaming audio |
| [llm-agents/local-text-chat-with-tavily-ollama](llm-agents/local-text-chat-with-tavily-ollama/) | Local model with optional web search — offline and online agent variants side by side | Ollama, Tavily, Python |

### Deployment & fine-tuning

| Project | Description | Stack |
|---|---|---|
| [llm-deployment/pllum-on-aws-ec2](llm-deployment/pllum-on-aws-ec2/) | Self-hosted Polish LLM on GPU instances, provisioned as code | HuggingFace, EC2, Terraform |
| [llm-deployment/aws-lambda-bedrock-tf](llm-deployment/aws-lambda-bedrock-tf/) | Serverless GenAI endpoint, pay-per-request | Bedrock, Lambda, Terraform |
| [llm-deployment/azure-openai](llm-deployment/azure-openai/) | LLM integration on Azure, with and without IaC | Azure OpenAI, Terraform |
| [fine-tuning/pllum-kaggle-pl](fine-tuning/pllum-kaggle-pl/) | Fine-tuning a Polish open model for a domain task | PyTorch, HuggingFace, PEFT |
| [fine-tuning/news-class](fine-tuning/news-class/) | Fine-tuned classifier for news categorization | Transformers, PyTorch |
| [llm-deployment/idps-aws-bedrock](llm-deployment/idps-aws-bedrock/) | Intelligent document processing — invoices in JPG, PDF and PNG parsed by a multimodal model | AWS Bedrock, Python |

### Computer vision

| Project | Description | Stack |
|---|---|---|
| [computer-vision/sign-language-recognition](computer-vision/sign-language-recognition/) | Gesture recognition from video — keypoint extraction, augmentation and classifier training, with local and cloud inference paths | MediaPipe, PyTorch, Azure |
| [computer-vision/ocr-source-evidence](computer-vision/ocr-source-evidence/) | Document data extraction compared three ways: regex, LLM, and managed OCR | Azure OCR, LLM API, Terraform |
| [computer-vision/object-tracking](computer-vision/object-tracking/) | Multi-object tracking across video frames | OpenCV, Python |
| [computer-vision/pose-estimation](computer-vision/pose-estimation/) | Human pose keypoint detection in real time | MediaPipe, OpenCV |

### Predictive modeling & optimization

| Project | Description | Stack |
|---|---|---|
| [water-network-optimization](ai/predictive-modeling-optimization/water-network-optimization/) | Hydraulic network optimization compared two ways: nonlinear solver vs piecewise linearization with SOS2 constraints | EPANET, Pyomo/MILP, Python |
| [predictive-modeling-optimization/scipy-optimization](predictive-modeling-optimization/scipy-optimization/) | Constrained and unconstrained optimization problems | SciPy, NumPy |
| [predictive-modeling-optimization/mobile-price-tf-aws-sagemaker](predictive-modeling-optimization/mobile-price-tf-aws-sagemaker/) | Classification model trained and deployed on SageMaker, infrastructure as code | scikit-learn, SageMaker, Terraform |
| [predictive-modeling-optimization/student-scores-prediction-gridsearch](predictive-modeling-optimization/student-scores-prediction-gridsearch/) | Full ML pipeline with modular components, hyperparameter search and a serving app | scikit-learn, Flask, pandas |
