# Generative AI: AWS Bedrock Blog Generator Demo

This demo deploys an **AWS Lambda function** that generates a short blog post using **Amazon Bedrock (Meta Llama 3)** and saves the result to an **S3 bucket**.

---

## Architecture

```
Lambda (Python) → Amazon Bedrock → Generated text → S3 bucket
```

- **Lambda** invokes Bedrock (Llama 3 model) to generate a blog post.  
- **S3** stores the generated output (`.txt` file).  
- **Terraform** handles provisioning IAM roles, Lambda, and S3.

---

## Requirements

- AWS CLI configured (`aws configure`)
- AWS account with:
  - Amazon Bedrock access (`meta.llama3-70b-instruct-v1:0`)
  - Permissions for Lambda, S3, CloudWatch
- Region: `us-east-1` (Bedrock fully supported)

---

## Setup

### 1. Initialize and deploy infrastructure

```bash
cd terraform
terraform init
terraform apply
```

**Example output:**
```bash
Outputs:

lambda_function_name = "bedrock-blog-generator"
s3_bucket_name       = "dartit-bedrock-blog-a3c678e5"
```

---

## Test the Lambda function

### Create input event
```bash
echo '{"blog_topic": "Edge computing"}' > event.json
```

### Invoke Lambda
```bash
aws lambda invoke   --function-name bedrock-blog-generator   --region us-east-1   --payload fileb://event.json   response.json
```

**Expected output:**
```json
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}
```

---

## View the results

### Inspect Lambda response

```bash
cat response.json
```

**Example output:**

```json
{"statusCode": 200, "body": "{"message": "OK", "s3_bucket": "dartit-bedrock-blog-a3c678e5", "s3_key": "blog-output/20251028T103809995706Z.txt"}"}
```

---

### List generated files in S3

```bash
aws s3 ls s3://dartit-bedrock-blog-a3c678e5/blog-output/
```

Example:
```
2025-10-28 11:38:11       1497 20251028T103809995706Z.txt
```

---

### Download and read the blog post

```bash
aws s3 cp s3://dartit-bedrock-blog-a3c678e5/blog-output/20251028T103809995706Z.txt .
cat 20251028T103809995706Z.txt
```

**Example content:**
```
Here's a 200-word blog post on edge computing:
**The Power of Edge Computing: Bringing Data Closer to Home**
In today's digital age, data is being generated at an unprecedented rate...
```

---

## Cost considerations

- **Pay only for usage**:
  - **Bedrock**: per input/output token (Llama 3 pricing)
  - **Lambda**: typically free under AWS Free Tier
  - **S3**: fractions of a cent per MB stored
  - **CloudWatch**: small cost for logs

---

## Cleanup

To remove all resources:
```bash
terraform destroy
```

---

## Notes

- Bedrock is **not available** in `eu-central-1` (Frankfurt).  
  Use `us-east-1` for model access.
- This demo uses a simple Bedrock call via `boto3` and saves output to S3 for inspection.
