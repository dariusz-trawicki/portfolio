# DevOps

Infrastructure as Code, container orchestration, GitOps, and automated delivery
across AWS and GCP.

**Certification:** HashiCorp Terraform Associate (003), 2025

## Categories

| Category | Focus |
|---|---|
| [iac](iac/) | Terraform, Terragrunt, Ansible — provisioning and configuration management |
| [kubernetes](kubernetes/) | Cluster deployments on EKS, GKE and Minikube |
| [gitops](gitops/) | Declarative delivery driven by Git as the source of truth |
| [ci-cd](ci-cd/) | Pipelines with GitHub Actions and Jenkins |

## Highlights

### Infrastructure as Code

| Project | Description | Stack |
|---|---|---|
| [aws-eks](iac/terraform/aws-eks/) | Managed Kubernetes cluster provisioned end to end | Terraform, AWS EKS |
| [aws-vpc-lb-github-actions](iac/terraform/aws-vpc-lb-github-actions/) | Network topology and load balancing, applied through CI with remote state | Terraform, AWS VPC, GitHub Actions, S3 |
| [aws-ec2-serve-llm-bielik](iac/terraform/aws-ec2-serve-llm-bielik/) | GPU instance provisioned and configured to serve a Polish LLM | Terraform, EC2, Docker |
| [gcp-cloud-run](iac/terraform/gcp-cloud-run/) | Serverless containers behind a load balancer on Google Cloud | Terraform, Cloud Run, GCP |
| [terragrunt/01-managing-remote-state](iac/terragrunt/01-managing-remote-state/) | Remote state management and DRY configuration across environments | Terragrunt, Terraform, S3 |
| [ansible/01-terraform-plus-ansible-demo](iac/ansible/01-terraform-plus-ansible-demo/) | Terraform provisions the infrastructure, Ansible configures the hosts — the standard IaC split between provisioning and configuration management | Terraform, Ansible, AWS |

### Kubernetes

| Project | Description | Stack |
|---|---|---|
| [aws-tf-eks-java-app](kubernetes/aws-tf-eks-java-app/) | Multi-tier Java application on EKS — app, database, RabbitMQ and Memcached, with persistent storage and ingress | EKS, Terraform, Kubernetes, Docker |
| [spark-on-minikube](kubernetes/spark-on-minikube/) | Spark master and workers running as Kubernetes-native workloads | Spark, Kubernetes, Minikube |
| [gcp-tf-gke-wordpress](kubernetes/gcp-tf-gke-wordpress/) | Stateful application on GKE with managed HTTPS, provisioned as code | GKE, Terraform, GCP |

### GitOps & CI/CD

| Project | Description | Stack |
|---|---|---|
| [argocd-canary](gitops/argocd-canary/) | Progressive delivery with canary rollouts and automated analysis, including a deliberately broken release to show rollback | ArgoCD, Argo Rollouts, Kubernetes |
| [ml-machines-efficiency](gitops/ml-machines-efficiency/) | ML model delivered to GKE declaratively — full project in [mlops](../mlops/gitops-gke-machines-efficiency/) | ArgoCD, GKE, Terraform |
| [github-actions](ci-cd/github-actions/) | Reusable workflows deploying to EKS/ECR and to EC2 with Terraform | GitHub Actions, Docker, Terraform |
| [jenkins/tf-eks-github](ci-cd/jenkins/tf-eks-github/) | Jenkins server provisioned as code, building and deploying to EKS with S3-backed state | Jenkins, Terraform, EKS |
| [jenkins/tf-ec2-with-docker-ci](ci-cd/jenkins/tf-ec2-with-docker-ci/) | Jenkins on EC2 with Docker-based CI, bootstrapped via user data | Jenkins, Terraform, EC2, Docker |
