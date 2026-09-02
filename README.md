# Portfolio

## Structure

- **[ai](ai/)**
  - [llm-rag](ai/llm-rag/) — retrieval-augmented generation, semantic search, agentic retrieval
  - [llm-agents](ai/llm-agents/) — function calling, tool use, voice agents
  - [llm-deployment](ai/llm-deployment/) — serving LLMs: managed, serverless, self-hosted
  - [fine-tuning](ai/fine-tuning/) — adapting open models to domain tasks
  - [llm-tooling](ai/llm-tooling/) — applied LLM utilities and skill-chain workflows
  - [computer-vision](ai/computer-vision/) — classification, tracking, pose estimation, OCR
  - [gen-ai](ai/gen-ai/) — generative image models
  - [predictive-modeling-optimization](ai/predictive-modeling-optimization/) — classical ML and mathematical optimization
- **[mlops](mlops/)** — experiment tracking, CI/CD for ML, drift monitoring, end-to-end pipelines
- **[data-engineering](data-engineering/)** — Kafka, Airflow, Spark, IoT streaming, ETL
- **[devops](devops/)** — Terraform, Terragrunt, Ansible, Kubernetes, GitOps, CI/CD

## Featured

| Project | What it does | Stack |
|---|---|---|
| [water-network-optimization](ai/predictive-modeling-optimization/water-network-optimization/) | Hydraulic network optimization: MILP with [piecewise linearization with SOS2 constraints](ai/predictive-modeling-optimization/water-network-optimization/piecewise-linearisation-demo/)| EPANET, Pyomo/MILP, Python |
| [gitops-gke-machines-efficiency](mlops/gitops-gke-machines-efficiency/) | ML model delivered to GKE declaratively — code, manifests and infrastructure in separate repos, synced by ArgoCD | GKE, Terraform, ArgoCD, GitHub Actions, Prometheus, Grafana |
| [with-llm-bielik-on-ec2](ai/llm-rag/with-llm-bielik-on-ec2/) | RAG over a self-hosted Polish LLM, with its own embedding service and vector store | Bielik, EC2, Docker, Terraform |
| [k8s-mlflow-data-drift-grafana](mlops/k8s-mlflow-data-drift-grafana/) | Model serving on Kubernetes with data drift detection and dashboards | Kubernetes, MLflow, Prometheus, Grafana |
| [bearing-fault-detection](mlops/bearing-fault-detection/) | Predictive maintenance end to end: streaming sensor data, feature extraction, model registry, serving API | Kafka, MLflow, Airflow, Postgres, Docker |
| [sign-language-recognition](ai/computer-vision/sign-language-recognition/) | Real-time gesture recognition from video, translating hand signs into text | OpenCV, MediaPipe, TensorFlow |
| [pllum-kaggle-pl](ai/fine-tuning/pllum-kaggle-pl/) | Fine-tuning an 8B Polish model for a domain-specific task | PyTorch, HuggingFace, PEFT |
| [iot-kafka-spark-promet-grafana](data-engineering/iot-kafka-spark-promet-grafana/) | Real-time IoT telemetry in three progressive architectures, from DB sink to stream processing | Kafka, Spark, MySQL, Prometheus, Grafana |
| [claude-code-core-skill-chain-workflow](ai/llm-tooling/claude-code-core-skill-chain-workflow/) | Agent workflow composed from chained skills — research, plan, implement, review as repeatable commands | Claude Code, MCP |


## Tech

- **ML / AI** — PyTorch, TensorFlow, scikit-learn, HuggingFace, LangChain, LangGraph, PydanticAI, Ollama, OpenCV
- **LLM** — RAG, semantic search, embeddings, fine-tuning (LoRA/PEFT), function calling, prompt engineering
- **Cloud** — AWS (Bedrock, SageMaker, EC2, Lambda, EKS, ECS, S3), GCP (Vertex AI, GKE, Cloud Run), Azure OpenAI
- **MLOps / DevOps** — MLflow, Airflow, Docker, Kubernetes, Terraform, Terragrunt, ArgoCD, Jenkins, GitHub Actions, Prometheus, Grafana
- **Data** — Kafka, Spark, PostgreSQL, MySQL, Elasticsearch


## Certifications & Training

**Certifications**
- HashiCorp Certified: Terraform Associate (003) — [2025]

**Selected courses (udemy.com etc.)**
- **Cloud & IaC** — Terraform (intro + GCP) · AWS Certified Cloud Practitioner · Google Cloud systems administration
- **MLOps** — Complete MLOps Bootcamp (10+ end-to-end ML projects) · MLOps on GCP: CI/CD, Kubernetes, Jenkins
- **DevOps** — Kubernetes from scratch · GitOps & real-time DevOps projects · Decoding DevOps: from basics to advanced
- **Data & tooling** — Apache Airflow: The Hands-On Guide · Docker · Git

<details>
<summary>Earlier background — web development (PHP / Symfony / Laravel)</summary>

**PHP frameworks**
- Symfony — Zbuduj aplikację mikroblog od podstaw
- Symfony & PHP Mastery: Build a Social Web App
- Zbuduj pierwszą aplikację w Symfony 6
- Laravel & PHP Mastery: Build 5 Real-World Projects
- Laravel Framework — wielkie kompendium programisty PHP
- Kurs Laravel — tworzenie aplikacji

**Frontend & CMS**
- Kurs HTML5 zaawansowany
- Kurs Tailwind CSS
- Kurs Bootstrap 3 / Bootstrap 4
- Kurs Foundation
- Tworzenie profesjonalnych stron z WordPress
- Tworzenie profesjonalnych sklepów z WooCommerce

**Other**
- Jira od podstaw: zarządzanie projektami Agile

<sub>Sources: udemy.com, strefakursow.pl</sub>
</details>

## Contact

[LinkedIn](https://www.linkedin.com/in/dariusz-trawicki-7809582b0/) · dariusz.trawicki@dartit.pl
