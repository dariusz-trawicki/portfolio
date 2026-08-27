import os

# gRPC's bundled c-ares resolver fails on macOS with some DNS setups
# (503 "DNS query cancelled"). Must be set before importing aiplatform.
os.environ["GRPC_DNS_RESOLVER"] = "native"

from kfp import compiler
from google.cloud import aiplatform
from pipeline import iris_pipeline

PROJECT_ID = os.environ["PROJECT_ID"]
REGION = os.environ["REGION"]
BUCKET = os.environ["BUCKET"]
SA = f"kfp-runner@{PROJECT_ID}.iam.gserviceaccount.com"

# 1. Compilation: Python functions -> YAML file describing the DAG
compiler.Compiler().compile(
    pipeline_func=iris_pipeline,
    package_path="iris_pipeline.yaml",
)

# 2. Client configuration
aiplatform.init(project=PROJECT_ID, location=REGION)

# 3. Job definition
job = aiplatform.PipelineJob(
    display_name="iris-demo",
    template_path="iris_pipeline.yaml",
    pipeline_root=f"{BUCKET}/pipeline-root",
    parameter_values={"n_estimators": 200},
    enable_caching=False,
)

# 4. Submission
job.submit(service_account=SA)

print("Submitted. Preview:")
print(
    f"https://console.cloud.google.com/vertex-ai/locations/{REGION}"
    f"/pipelines/runs/{job.name}?project={PROJECT_ID}"
)
