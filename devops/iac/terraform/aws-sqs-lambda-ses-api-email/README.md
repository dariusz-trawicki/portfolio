## SQS → Lambda → SES Email Sender (Terraform + AWS)

This example shows how to send emails via **Amazon SES** using a fully
serverless pipeline:

**SQS → Lambda (Python) → SES**

Messages are pushed to an `SQS queue`, processed by a `Lambda function`, and
sent via `SES`.

------------------------------------------------------------------------

### Architecture Overview

Components:

1.  **Amazon SES**
    -   Domain identity, e.g.: `dartit.pl`
    -   DKIM enabled
    -   Used to send email from e.g. `dariusz.trawicki@dartit.pl`.
2.  **Amazon SQS**
    -   Queue: `email-send-queue`
    -   Stores email job messages as JSON.
3.  **AWS Lambda**
    -   Function: `send-email-from-sqs`
    -   Runtime: Python 3.12
    -   Triggered by SQS
    -   Sends emails using boto3 → SES.
4.  **IAM**
    -   Permissions for SQS receive/delete
    -   Permissions for SES send email
    -   CloudWatch logging

------------------------------------------------------------------------

### Terraform Overview

Includes:

-   SES domain + DKIM
-   SQS queue
-   IAM role + policies
-   Lambda function
-   Event source mapping SQS → Lambda
-   Packaging Lambda via `archive_file`

Example resource snippets:

#### SES

``` hcl
resource "aws_ses_domain_identity" "dartit" {
  domain = var.domain # "dartit.pl"
}

resource "aws_ses_domain_dkim" "dartit" {
  domain = aws_ses_domain_identity.dartit.domain
}
```

#### SQS

``` hcl
resource "aws_sqs_queue" "email_queue" {
  name = "email-send-queue"
  visibility_timeout_seconds = 60
}
```

#### Lambda Function

``` hcl
locals {
  ses_from_email = var.sender_address # "dariusz.trawicki@dartit.pl"
}

resource "aws_lambda_function" "send_email" {
  function_name = "send-email-from-sqs"
  role          = aws_iam_role.lambda_role.arn
  handler       = "send_email.handler"
  runtime       = "python3.12"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      SES_FROM_EMAIL = local.ses_from_email
    }
  }
}
```

#### SQS → Lambda Trigger

``` hcl
resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.email_queue.arn
  function_name    = aws_lambda_function.send_email.arn
  batch_size       = 10
  enabled          = true
}
```

#### Apply

``` bash
cd terraform
terraform init
terraform apply
```

#### SES Sandbox Notes

If SES is in sandbox mode:

-   You must verify every **sender** and **recipient** email.
-   To send freely, request **production access** in SES console.


#### Terraform Outputs
Terraform prints:
- the TXT record for verification,
- three DKIM CNAME records.

Paste them manually in your `DNS provider`.

#### Example Outputs

```bash
ses_dkim_records = [
  {
    "name" = "woijkxvw6hshle25lqacyerlfnpkmsas._domainkey.dartit.pl"
    "type" = "CNAME"
    "value" = "woijkxvw6hshle25lqacyerlfnpkmsas.dkim.amazonses.com"
  },
  {
    "name" = "cnmaerydv5cus6u2jrkehknxvyko4tfe._domainkey.dartit.pl"
    "type" = "CNAME"
    "value" = "cnmaerydv5cus6u2jrkehknxvyko4tfe.dkim.amazonses.com"
  },
  {
    "name" = "dfam5exnppdqth7ccbc5t2hpnnbk3xtd._domainkey.dartit.pl"
    "type" = "CNAME"
    "value" = "dfam5exnppdqth7ccbc5t2hpnnbk3xtd.dkim.amazonses.com"
  },
]
ses_verification_txt_name = "_amazonses.dartit.pl"
ses_verification_txt_value = "JL93rU+LZPRheY0b8rO2Bqn4z6h04OV6Yy7G0wq7Op4="
```

These values must be pasted into your `DNS provider` (Cloudflare, OVH, GoDaddy, etc.).

### Adding DNS Records in Your DNS Provider (General Instructions)

Regardless of the DNS provider, the steps are usually:

1. Open the DNS management panel for your domain.
2. Make sure manual DNS configuration is enabled.
3. Add the Terraform-generated records:

#### **1. TXT record – domain verification**

- **Name:** `_amazonses.dartit.pl`
- **Type:** TXT
- **Value:** `JL93rU+LZPRheY0b8rO2Bqn4z6h04OV6Yy7G0wq7Op4=`
- TTL: default value is fine.

#### **2. DKIM – three CNAME records**

Each DKIM key must be added as a **separate** CNAME record.

#### DKIM 1
- Name: `woijkxvw6hshle25lqacyerlfnpkmsas._domainkey.dartit.pl`
- Type: `CNAME`
- Value: `woijkxvw6hshle25lqacyerlfnpkmsas.dkim.amazonses.com`

#### DKIM 2
- Name: `cnmaerydv5cus6u2jrkehknxvyko4tfe._domainkey.dartit.pl`
- Type: `CNAME`
- Value: `cnmaerydv5cus6u2jrkehknxvyko4tfe.dkim.amazonses.com`

#### DKIM 3
- Name: `dfam5exnppdqth7ccbc5t2hpnnbk3xtd._domainkey.dartit.pl`
- Type: `CNAME`
- Value: `dfam5exnppdqth7ccbc5t2hpnnbk3xtd.dkim.amazonses.com`

---

## Verification in AWS SES

After adding the DNS records:

- **Wait several minutes** (DNS propagation can take 5–30 minutes).
- Go to (example):  
  **AWS Console → SES → Verified identities → dartit.pl**

You should see:

- **Domain status:** Verified
- **DKIM:** Verified / Successful

Once both are green, you can reliably send email from (example): `dariusz.trawicki@dartit.pl` via Amazon SES (SMTP or API).

---

## SES Sandbox Requirements

If your SES account is in **SANDBOX mode**, you must:

- verify every **recipient email address** before sending,
- AWS sends a `verification link` to confirm ownership.

Example: to send email to `dt.dartit@gmail.com`, you must verify that address first.

---

## Testing Email Delivery in the SES Console

Navigate to (example):

**SES → Configuration → Identities → dartit.pl → Send test email**

Use:

- **From:** `dariusz.trawicki@dartit.pl`
- **Scenario:** Custom
- **Recipient:** e.g., `dt.dartit@gmail.com`
- **Subject / Body:** any text

If DNS and verification are correct, the email should be delivered.

---

### Testing the Flow

``` bash
# 1. Get queue URL
QUEUE_URL=$(aws sqs get-queue-url   --queue-name email-send-queue   --query 'QueueUrl'   --output text)

# 2. Send a test message
aws sqs send-message   --queue-url "$QUEUE_URL"   --message-body '{
    "to": "dt.dartit@gmail.com",
    "subject": "Test from SQS -> Lambda -> SES",
    "body": "Hi! This email is being sent through the SQS queue and Lambda :)"
  }'
# Output (example):
# {
#     "MD5OfMessageBody": "c1cda55a46d1111543b5229d2b309555",
#     "MessageId": "96c01da4-afa2-4ff1-932a-a683cca7025a"
# }
```

### Testing / running via JavaScript

1. Install the SQS client

```bash
cd ..
npm install @aws-sdk/client-sqs
```

2. Run the JS script

```bash
# Fetch the queue URL and export it as an environment variable
export QUEUE_URL=$(aws sqs get-queue-url \
  --queue-name email-send-queue \
  --query 'QueueUrl' \
  --output text)

# Set the AWS region
export AWS_REGION=eu-central-1

# Execute the script
node sendEmailMessage.js
# Example output:
# Message sent! ID: 3cf57788-0121-4913-8904-23ce3f49d040
```
