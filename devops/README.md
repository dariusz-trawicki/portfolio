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
| [iac/terraform/eks](iac/terraform/eks/) | Managed Kubernetes cluster provisioned end to end | Terraform, AWS EKS |
| [iac/terraform/vpc-lb-github-actions](iac/terraform/vpc-lb-github-actions/) | Network topology and load balancing, applied through CI | Terraform, AWS VPC, GitHub Actions |
| [iac/terragrunt](iac/terragrunt/) | Remote state management and DRY configuration across environments | Terragrunt, Terraform, S3 |
| [iac/ansible](iac/ansible/) | Terraform provisions the infrastructure, Ansible configures the hosts — the standard IaC split between provisioning and configuration management | Terraform, Ansible, AWS |

### Kubernetes

| Project | Description | Stack |
|---|---|---|
| [kubernetes/aws-tf-eks-java-app](kubernetes/aws-tf-eks-java-app/) | Java application deployed to EKS with infrastructure as code | EKS, Terraform, Docker |
| [kubernetes/spark-on-minikube](kubernetes/spark-on-minikube/) | Spark running as Kubernetes-native workloads | Spark, Kubernetes, Minikube |
| [kubernetes/gcp-tf-gke-wordpress](kubernetes/gcp-tf-gke-wordpress/) | Stateful application on GKE, provisioned and configured as code | GKE, Terraform, Helm |

### GitOps & CI/CD

| Project | Description | Stack |
|---|---|---|
| [gitops/argocd-canary](gitops/argocd-canary/) | Progressive delivery with canary rollouts driven from Git | ArgoCD, Kubernetes |
| [gitops/ml-machines-efficiency](gitops/ml-machines-efficiency/) | ML model delivered to GKE declaratively — *see [mlops](../mlops/gitops-gke-machines-efficiency/)* | ArgoCD, GKE, Terraform |
| [ci-cd/github-actions](ci-cd/github-actions/) | Reusable workflows for containers, Terraform, EKS and ECS | GitHub Actions, Docker, Terraform |
| [ci-cd/jenkins](ci-cd/jenkins/) | Jenkins on EC2 and EKS, provisioned as code | Jenkins, Terraform, AWS |
