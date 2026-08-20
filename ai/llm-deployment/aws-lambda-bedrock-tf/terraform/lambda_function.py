import os
import json
import boto3
import botocore.config
from datetime import datetime, timezone

BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
MODEL_ID = os.getenv("MODEL_ID", "meta.llama3-70b-instruct-v1:0")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "blog-output/")

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=BEDROCK_REGION,
    config=botocore.config.Config(read_timeout=300, retries={"max_attempts": 3}),
)
s3 = boto3.client("s3")

def _sanitize_topic(topic: str) -> str:
    topic = (topic or "").strip()
    for bad in ("[/INST]", "<s>", "</s>"):
        topic = topic.replace(bad, "")
    return topic

def blog_generate_using_bedrock(blogtopic: str) -> str:
    topic = _sanitize_topic(blogtopic)
    prompt = f"""<s>[INST]
Human: Write a 200-word blog post on the topic "{topic}".
Use a friendly tone, include an intro, 2-3 short paragraphs, and a one-sentence conclusion.
[/INST]
"""
    body = {"prompt": prompt, "max_gen_len": 400, "temperature": 0.5, "top_p": 0.9}
    try:
        response = bedrock.invoke_model(
            body=json.dumps(body),
            modelId=MODEL_ID,
            accept="application/json",
            contentType="application/json",
        )
        payload = response.get("body").read()
        data = json.loads(payload)
        return (data.get("generation") or "").strip()
    except Exception as e:
        print(f"[ERROR] Bedrock invoke failed: {e}")
        return ""

def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

def save_to_s3(key: str, contents: str):
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=contents.encode("utf-8"))

def lambda_handler(event, context):
    try:
        raw_body = event.get("body", event) if isinstance(event, dict) else event
        body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON body"})}

    topic = body.get("blog_topic")
    if not isinstance(topic, str) or not topic.strip():
        return {"statusCode": 400, "body": json.dumps({"error": "Missing 'blog_topic'"})}

    text = blog_generate_using_bedrock(topic)
    if not text:
        return {"statusCode": 502, "body": json.dumps({"error": "Generation failed"})}

    key = f"{S3_PREFIX}{_utc_timestamp()}.txt"
    try:
        save_to_s3(key, text)
    except Exception as e:
        print(f"[ERROR] S3 put_object failed: {e}")
        return {"statusCode": 502, "body": json.dumps({"error": "S3 save failed"})}

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "OK", "s3_bucket": S3_BUCKET, "s3_key": key}),
    }
