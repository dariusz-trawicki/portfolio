# Portfolio

## Structure

- **[ai](ai/)** — [RAG](ai/llm-rag/), [agents](ai/llm-agents/), [fine-tuning](ai/fine-tuning/), [LLM deployment](ai/llm-deployment/), [computer vision](ai/computer-vision/), [generative models](ai/gen-ai/), [predictive modeling & optimization](ai/predictive-modeling-optimization/)
- **[mlops](mlops/)** — experiment tracking, CI/CD for ML, drift monitoring, end-to-end pipelines
- **[data-engineering](data-engineering/)** — Kafka, Airflow, Spark, IoT streaming, ETL
- **[devops](devops/)** — Terraform, Terragrunt, Ansible, Kubernetes, GitOps, CI/CD

## Featured

| Project | What it does | Stack |
|---|---|---|
| [gitops-gke-machines-efficiency](mlops/gitops-gke-machines-efficiency/) | ML model delivered to GKE declaratively — code, manifests and infrastructure in separate repos, synced by ArgoCD | ArgoCD, GKE, Terraform, GitHub Actions |
| [with-llm-bielik-on-ec2](ai/llm-rag/with-llm-bielik-on-ec2/) | RAG over a self-hosted Polish LLM, with its own embedding service and vector store | Bielik, EC2, Docker, Terraform |
| [k8s-mlflow-data-drift-grafana](mlops/k8s-mlflow-data-drift-grafana/) | Model serving on Kubernetes with data drift detection and dashboards | Kubernetes, MLflow, Prometheus, Grafana |
| [bearing-fault-detection](mlops/bearing-fault-detection/) | Predictive maintenance end to end: streaming sensor data, feature extraction, model registry, serving API | Kafka, MLflow, Airflow, Postgres, Docker |
| [claude-code-core-skill-chain-workflow](ai/llm-tooling/claude-code-core-skill-chain-workflow/) | Agent workflow composed from chained skills — research, plan, implement, review as repeatable commands | Claude Code, MCP |
| [sign-language-recognition](ai/computer-vision/sign-language-recognition/) | Real-time gesture recognition from video, translating hand signs into text | OpenCV, MediaPipe, TensorFlow |
| [pllum-kaggle-pl](ai/fine-tuning/pllum-kaggle-pl/) | Fine-tuning an 8B Polish model for a domain-specific task | PyTorch, HuggingFace, PEFT |
| [iot-kafka-spark-promet-grafana](data-engineering/iot-kafka-spark-promet-grafana/) | Real-time IoT telemetry in three progressive architectures, from DB sink to stream processing | Kafka, Spark, MySQL, Prometheus, Grafana |


## Tech

- **ML / AI** — PyTorch, TensorFlow, scikit-learn, HuggingFace, LangChain, LangGraph, PydanticAI, Ollama, OpenCV
- **LLM** — RAG, semantic search, embeddings, fine-tuning (LoRA/PEFT), function calling, prompt engineering
- **Cloud** — AWS (Bedrock, SageMaker, EC2, Lambda, EKS, ECS, S3), GCP (Vertex AI, GKE, Cloud Run), Azure OpenAI
- **MLOps / DevOps** — MLflow, Airflow, Docker, Kubernetes, Terraform, Terragrunt, ArgoCD, Jenkins, GitHub Actions, Prometheus, Grafana
- **Data** — Kafka, Spark, PostgreSQL, MySQL, Elasticsearch


## Contact

[LinkedIn](https://www.linkedin.com/in/dariusz-trawicki-7809582b0/) · dariusz.trawicki@dartit.pl
