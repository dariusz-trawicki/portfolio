# Iris MLOps — End-to-End GitOps on GKE

A PyTorch classifier deployed to Google Kubernetes Engine through ArgoCD, with no static credentials anywhere in the pipeline, images pinned by digest rather than tag, and promotion from dev to prod gated behind a pull request.

The model itself is deliberately trivial — a three-layer MLP on the Iris dataset. Everything interesting is in the delivery path around it.

- **The code**:
  - [`gitops-gke-iris-kustomize`](https://github.com/dariusz-trawicki/portfolio/tree/main/mlops/gitops-gke-iris-kustomize)
