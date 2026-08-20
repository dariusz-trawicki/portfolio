## Amazon SES (Simple Email Service) demo


### Purpose of This Demo

The goal of this demo is to provide a simple, fully reproducible example of how to:

1. **Configure Amazon SES (Simple Email Service) for a custom domain** using Terraform.  
2. **Verify a domain** in SES by generating the required DNS records (TXT + DKIM).  
3. **Set up DKIM** to improve email deliverability and prevent messages from being marked as spam.  
4. **Manually add DNS records** when your DNS is hosted outside AWS (e.g. Cloudflare, OVH, GoDaddy).  
5. **Test email sending** directly from the AWS SES console.  
6. **Send emails programmatically** using Node.js and the AWS SDK.

### Terraform

- Enables **Amazon SES** for a given domain (example: `dartit.pl`).  
- Creates in SES:
  - a **domain identity** (domain verification),
  - **DKIM keys** (to improve email deliverability and prevent spam classification).

My email inbox is `dariusz.trawicki@dartit.pl`, so the root domain used in SES is **dartit.pl**.  
My DNS is hosted at **nazwa.pl**, therefore all DNS records (`TXT` and `CNAME`) must be added **manually** in their DNS panel (the same applies to any external DNS provider).

#### Running Terraform

```bash
terraform init
terraform apply
```


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

### Sending Emails Using Node.js

```bash
npm install @aws-sdk/client-ses
node ses-send-email.js
```

### How Authentication to AWS Works in the Node.js Example

In the Node.js code:

```js
const { SESClient, SendEmailCommand } = require("@aws-sdk/client-ses");

const ses = new SESClient({ region: "eu-central-1" });
```

you don’t see any explicit “login” or credentials being passed (no access key, no secret key, no password).  
Authentication happens **behind the scenes** when you create `SESClient` and call:

```js
await ses.send(new SendEmailCommand(params));
```

The AWS SDK for JavaScript (v3) uses the **default credential provider chain**.  
That means it automatically looks for credentials in a predefined order, for example:

#### 1. Environment variables

```bash
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
# (optional) for temporary credentials
export AWS_SESSION_TOKEN=YOUR_SESSION_TOKEN
```

#### 2. Shared credentials/config files

Usually located in:

- `~/.aws/credentials`
- `~/.aws/config`

Example:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

You can also select a profile with:

```bash
export AWS_PROFILE=your-profile-name
```

#### 3. IAM Role (when running on AWS services)

If the code runs inside AWS (e.g., **EC2**, **ECS**, **EKS**, **Lambda**),  
the SDK automatically retrieves **temporary credentials** from the IAM role attached to that resource.

No keys are stored locally — permissions come from the role.

#### 4. Other mechanisms

Such as AWS SSO or web identity tokens, if configured.

---

As soon as the SDK finds valid credentials with permissions like:

- `ses:SendEmail`
- `ses:SendRawEmail` (optional)

the call:

```js
await ses.send(new SendEmailCommand(params));
```

will be authorized and SES will send the email.

If no valid credentials are found, or permissions are insufficient,  
AWS SDK will throw an **authorization error**.

