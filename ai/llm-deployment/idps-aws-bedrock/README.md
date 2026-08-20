# Intelligent Document Processing System (IDPS)

A Streamlit demo app that combines **Amazon Textract** (OCR) with **Amazon Bedrock / Claude** (Q&A) to extract text from images and PDFs and answer questions about their content.

---

## Architecture

```
User uploads image/PDF
        │
        ▼
  Amazon Textract
  (detect_document_text)
        │
        ▼
  Extracted text + bounding boxes
        │
        ▼
  Amazon Bedrock (Claude 3.5 Haiku)
  (question answering over context)
        │
        ▼
  Answer displayed in Streamlit UI
```

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- AWS account with access to:
  - **Amazon Textract** (region: `us-east-1` or your chosen region)
  - **Amazon Bedrock** with model access granted for `claude-3-5-haiku-20241022`

---

## Setup

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
streamlit run app.py
```

---

## AWS Credentials

Choose one of the following methods:

### Option A — Environment variables (recommended for local dev)

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

### Option B — AWS CLI profile

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, region (us-east-1), output format (json)
```

Boto3 will pick up `~/.aws/credentials` automatically.

---

## Enable Bedrock Model Access

Before first use, enable the Claude model in the AWS Console:

1. Open **Amazon Bedrock** → **Model catalog**
2. Find `Claude 3.5 Haiku` under `Anthropic`
3. Click **Request access** → confirm

---

## Running the App

```bash
streamlit run streamlitapp.py
```

The app will open at `http://localhost:8501`.

---

## Usage

1. Open the app in your browser
2. Upload a file — supported formats: `PNG`, `JPG`, `JPEG`, `TIFF`, `PDF`
    - folder: `/sample_docs`.
3. The app will:
   - Convert PDF pages to images (if applicable)
   - Send each page to Amazon Textract for OCR
   - Display extracted text and bounding box visualization
4. Type a question in the **Document Question Answering** section
  - example: `Invoice number?`
5. Claude (via Bedrock) will answer based on the extracted text

---

## Supported File Types

| Format | Notes                                      |
|--------|--------------------------------------------|
| PNG    | Direct upload to Textract                  |
| JPG    | Direct upload to Textract                  |
| TIFF   | Direct upload to Textract                  |
| PDF    | Rendered page-by-page via PyMuPDF (fitz)   |

> Textract's synchronous API (`detect_document_text`) does **not** accept PDF bytes directly — the app converts each PDF page to PNG first.

---

## Environment Variables

| Variable               | Default      | Description                        |
|------------------------|--------------|------------------------------------|
| `AWS_ACCESS_KEY_ID`    | —            | AWS access key (if not using CLI)  |
| `AWS_SECRET_ACCESS_KEY`| —            | AWS secret key (if not using CLI)  |
| `AWS_REGION`           | `us-east-1`  | AWS region for Textract + Bedrock  |

---

## Cost Estimate (AWS)

| Service         | Pricing                                      |
|-----------------|----------------------------------------------|
| Textract        | ~$1.50 per 1,000 pages (detect_document_text)|
| Bedrock / Haiku | ~$0.001 per 1K input tokens                  |

For demo usage the cost is negligible. Monitor via **AWS Cost Explorer**.
