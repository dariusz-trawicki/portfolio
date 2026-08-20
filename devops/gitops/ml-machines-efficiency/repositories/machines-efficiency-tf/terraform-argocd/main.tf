resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true

  # Small nodes pull images slowly; the default 300s is optimistic.
  timeout = 900
  wait    = true

  values = [yamlencode({
    configs = {
      params = {
        # Plain HTTP behind port-forward - no TLS to terminate
        "server.insecure" = true
      }
    }
    server = {
      # ClusterIP keeps the UI off the internet and off the bill.
      # Switch to LoadBalancer only after configuring real authentication.
      service   = { type = "ClusterIP" }
      resources = { requests = { cpu = "50m", memory = "128Mi" } }
    }
    controller = {
      resources = { requests = { cpu = "100m", memory = "256Mi" } }
    }
    repoServer = {
      resources = { requests = { cpu = "50m", memory = "128Mi" } }
    }
    # Not needed for a single Application - saves memory on a small cluster
    applicationSet = { enabled = false }
    # No SSO in a demo
    dex = { enabled = false }
  })]
}

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_namespace
  }
}

# ---------------------------------------------------------------------------
# The ArgoCD Application.
#
# Deployed through the argocd-apps Helm chart rather than kubernetes_manifest,
# because kubernetes_manifest validates CRDs at PLAN time - and the Application
# CRD does not exist until the release above is applied. Helm renders at apply
# time, so a single `terraform apply` works.
# ---------------------------------------------------------------------------
resource "helm_release" "argocd_apps" {
  name       = "argocd-apps"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = var.argocd_apps_chart_version
  namespace  = "argocd"

  values = [yamlencode({
    applications = {
      (var.app_name) = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.config_repo_url
          targetRevision = var.config_repo_revision
          path           = var.config_repo_path
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = var.app_namespace
        }
        syncPolicy = {
          automated = {
            prune    = true # remove resources deleted from Git
            selfHeal = true # revert manual kubectl edits
          }
          syncOptions = ["CreateNamespace=true"]
        }
      }
    }
  })]

  depends_on = [
    helm_release.argocd,
    kubernetes_namespace.app,
  ]
}

resource "kubernetes_secret" "config_repo" {
  metadata {
    name      = "config-repo"
    namespace = "argocd"
    labels = {
      "argocd.argoproj.io/secret-type" = "repository"
    }
  }

  data = {
    type          = "git"
    url           = var.config_repo_url
    sshPrivateKey = file(pathexpand(var.config_repo_ssh_key_path))
  }

  depends_on = [helm_release.argocd]
}
