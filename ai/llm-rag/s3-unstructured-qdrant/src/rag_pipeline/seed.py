"""Entry point: creates the bucket and uploads the sample documents to S3."""

import argparse
from pathlib import Path

import boto3

from rag_pipeline.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload local files to the S3 bucket.")
    parser.add_argument("directory", nargs="?", default="sample_docs", help="Folder to upload")
    args = parser.parse_args()

    settings = Settings.from_env()
    s3 = boto3.client("s3")

    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        s3.create_bucket(Bucket=settings.s3_bucket)
        print(f"Created bucket: {settings.s3_bucket}")

    files = sorted(p for p in Path(args.directory).iterdir() if p.is_file())
    for path in files:
        key = f"{settings.s3_prefix}{path.name}"
        s3.upload_file(str(path), settings.s3_bucket, key)
        print(f"Uploaded: s3://{settings.s3_bucket}/{key}")

    print(f"\n{len(files)} files uploaded.")


if __name__ == "__main__":
    main()
