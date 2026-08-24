terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    # Used instead of kubernetes_manifest for the CRD-based resources.
    # See the comment above kubectl_manifest.secret_store below.
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.19"
    }
  }
}

################################################################################
# Cluster lookup
#
# Data sources rather than remote state: this stage only needs the cluster
# name, which keeps the two stages loosely coupled.
################################################################################

provider "aws" {
  region = var.region
}

data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "this" {
  name = var.cluster_name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "kubectl" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
  load_config_file       = false
}

################################################################################
# External Secrets Operator
################################################################################

resource "helm_release" "eso" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = var.eso_chart_version
  namespace        = "external-secrets"
  create_namespace = true

  # CRDs define the ExternalSecret and SecretStore kinds. Without them,
  # the manifests below fail with "no matches for kind".
  set {
    name  = "installCRDs"
    value = "true"
  }

  # The service account name must match the Pod Identity association
  # created in stage 01.
  set {
    name  = "serviceAccount.name"
    value = "external-secrets"
  }
}

################################################################################
# SecretStore - where to read from, and how to authenticate
#
# NOTE: there is deliberately no `auth` block.
#
# With EKS Pod Identity, the agent injects AWS_CONTAINER_CREDENTIALS_FULL_URI
# into the pod and the AWS SDK picks it up through its default credential
# chain. ESO does not need to request anything.
#
# Most tutorials show the IRSA variant instead:
#
#   auth:
#     jwt:
#       serviceAccountRef:
#         name: external-secrets
#
# Copying that here produces an authentication failure.
################################################################################

# kubectl_manifest rather than kubernetes_manifest:
# kubernetes_manifest validates the manifest against the live API server
# during `terraform plan`, which runs before the Helm release has installed
# the CRDs. depends_on does not help, because it only affects apply ordering.
resource "kubectl_manifest" "secret_store" {
  depends_on = [helm_release.eso]

  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1
    kind: SecretStore
    metadata:
      name: aws
      namespace: ${var.app_namespace}
    spec:
      provider:
        aws:
          service: SecretsManager
          region: ${var.region}
  YAML
}

################################################################################
# ExternalSecret - what to fetch and where to put it
#
# Direction of the mapping:
#   remoteRef.key      -> secret name in AWS
#   remoteRef.property -> field inside that secret's JSON
#   secretKey          -> key name in the resulting Kubernetes Secret
#   target.name        -> name of the Kubernetes Secret to create
################################################################################

resource "kubectl_manifest" "external_secret" {
  depends_on = [kubectl_manifest.secret_store]

  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1
    kind: ExternalSecret
    metadata:
      name: orders-api
      namespace: ${var.app_namespace}
    spec:
      refreshInterval: ${var.refresh_interval}
      secretStoreRef:
        name: aws
        kind: SecretStore
      target:
        name: orders-api-secret
      data:
        - secretKey: DB_PASSWORD
          remoteRef:
            key: ${var.secret_name}
            property: password
        - secretKey: DB_USERNAME
          remoteRef:
            key: ${var.secret_name}
            property: username
  YAML
}

################################################################################
# Reloader (optional)
#
# Closes the last gap in the chain. ESO keeps the Kubernetes Secret in sync
# with AWS, but a running pod read its environment variables once at startup
# and never looks again. Reloader watches Secrets and restarts the workloads
# that consume them.
#
# Disabled by default so the gap can be observed first - see the README.
################################################################################

resource "helm_release" "reloader" {
  count = var.enable_reloader ? 1 : 0

  name             = "reloader"
  repository       = "https://stakater.github.io/stakater-charts"
  chart            = "reloader"
  namespace        = "reloader"
  create_namespace = true
}
