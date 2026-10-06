# The agent as a container. Built for the CPU of the machine that builds it
# (arm64 on Apple Silicon), loaded into kind with `make agent-image`.
#
#   docker build -t incident-agent:dev .

# ---- 1) Python dependencies in a virtualenv (build tools stay in this stage)
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/venv/bin/pip install ".[postgres]"

# ---- 2) kubectl: the executor runs `kubectl rollout undo` (the same command a human would run).
# Downloaded with its checksum and verified; TARGETARCH is set by Docker BuildKit (amd64 / arm64).
FROM python:3.12-slim AS kubectl
ARG KUBECTL_VERSION=v1.34.1
ARG TARGETARCH
ADD https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl /kubectl
ADD https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl.sha256 /kubectl.sha256
RUN echo "$(cat /kubectl.sha256)  /kubectl" | sha256sum -c - && chmod 0755 /kubectl

# ---- 3) runtime: no compilers, no pip cache, a non-root user
FROM python:3.12-slim
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin agent
COPY --from=build /opt/venv /opt/venv
COPY --from=kubectl /kubectl /usr/local/bin/kubectl
# HOME=/tmp: kubectl keeps its discovery cache there (the root filesystem is read-only in the pod)
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /tmp
USER 10001
EXPOSE 8787
ENTRYPOINT ["incident-agent"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8787", "--out-dir", "/tmp/reports"]
