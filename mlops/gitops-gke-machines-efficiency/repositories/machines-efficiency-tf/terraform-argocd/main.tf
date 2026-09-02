# ---------------------------------------------------------------------------
# Root Application (app-of-apps).
#
# Describes no component of its own - it only points at the apps/ directory in
# the config repo, where the actual Application objects live (ML app, monitoring).
# Adding something to the cluster is a Git commit from here on, not a
# `terraform apply`.
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
      root = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.config_repo_url
          targetRevision = var.config_repo_revision
          path           = "apps"
        }
        destination = {
          server = "https://kubernetes.default.svc"
          # Application objects must live in the ArgoCD namespace - that is the
          # only place the controller looks. CreateNamespace is unnecessary
          # because the argocd namespace already exists.
          namespace = "argocd"
        }
        syncPolicy = {
          automated = {
            prune    = true # remove Applications deleted from apps/
            selfHeal = true # revert manual kubectl edits
          }
        }
      }
    }
  })]

  depends_on = [helm_release.argocd]
}

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
      service   = { type = "ClusterIP" }
      resources = { requests = { cpu = "50m", memory = "128Mi" } }
      metrics   = { enabled = true, serviceMonitor = { enabled = true } }
    }
    controller = {
      resources = { requests = { cpu = "100m", memory = "256Mi" } }
      metrics   = { enabled = true, serviceMonitor = { enabled = true } }
    }
    repoServer = {
      resources = { requests = { cpu = "50m", memory = "128Mi" } }
      metrics   = { enabled = true, serviceMonitor = { enabled = true } }
    }
    # App-of-apps uses plain Applications in a directory - ApplicationSet is
    # only needed for generating them from a list (e.g. one per environment).
    applicationSet = { enabled = false }
    # No SSO in a demo
    dex = { enabled = false }
  })]
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
