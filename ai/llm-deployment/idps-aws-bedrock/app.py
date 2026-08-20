import streamlit as st
import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw
import io
import json
import os
import fitz  # PyMuPDF
from typing import Dict, List, Optional

### AWS Config 
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Boto3 reads credentials automatically:
#   - from env vars (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
#   - from ~/.aws/credentials  (after `aws configure`)
session = boto3.Session()
# Amazon Textract — OCR + table/form extraction from documents
textract = session.client('textract', region_name=AWS_REGION)

# Amazon Bedrock Runtime — querying LLM models via API
bedrock_runtime = session.client('bedrock-runtime', region_name=AWS_REGION)

### Streamlit UI
st.set_page_config(page_title='IDPS Demo', layout='centered')
st.title('Intelligent Document Processing System with Q&A')
st.markdown('Upload an image or PDF for text extraction, visualization, and question answering.')

uploaded_file = st.file_uploader(
    'Upload document',
    type=['png', 'jpg', 'jpeg', 'tiff', 'pdf']
)


def pdf_to_images(file_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """
    Converts each PDF page to a PIL Image.

    Textract does not accept PDF directly via Bytes (only via S3),
    so we render pages as PNG and pass them as images.

    Args:
        file_bytes: raw bytes of the PDF file
        dpi:        rendering resolution (200 = good quality/speed balance)

    Returns:
        List of PIL.Image objects — one page per element
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for page in doc:
        # Matrix scales the page: PyMuPDF base resolution is 72 DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    doc.close()
    return images


def extract_text_from_response(response: Dict) -> str:
    """
    Extracts text from a Textract response in reading order.

    Textract returns a list of Blocks of different types:
      PAGE  -> entire page
      LINE  -> line of text  <- filtered here
      WORD  -> single word

    Returns:
        Text joined with newlines
    """
    blocks = response.get('Blocks', [])
    lines = [b for b in blocks if b['BlockType'] == 'LINE']
    return '\n'.join([line['Text'] for line in lines])


def process_document_for_qa(file_bytes: bytes) -> Optional[Dict]:
    """
    Sends image bytes to Amazon Textract and returns the raw response.

    Uses synchronous detect_document_text (no S3 required).
    Limit: images up to 10 MB, documents up to 3000 pages (via S3 + async).

    Returns:
        Dictionary with Textract response or None on error
    """
    try:
        response = textract.detect_document_text(Document={'Bytes': file_bytes})
        return response
    except ClientError as e:
        st.error(f"AWS Textract error: {e}")
        return None


def ask_bedrock_question(context: str, question: str) -> Optional[str]:
    """
    Sends a question and document context to a Claude model via Amazon Bedrock.

    Args:
        context:  text extracted by Textract (may span multiple pages)
        question: user's question

    Returns:
        Model response as a string or None on error
    """
    prompt = f"""Human: You are a helpful assistant that answers questions based on the provided document context.

Document Context:
{context}

Question: {question}

A:"""

    try:
        response = bedrock_runtime.invoke_model(
            modelId="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.5,
                "top_p": 0.9,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }),
            contentType="application/json",
        )
        result = json.loads(response['body'].read())
        return result['content'][0]['text'].strip()
    except ClientError as e:
        st.error(f"AWS Bedrock error: {e}")
        return None


def draw_bounding_boxes(image: Image.Image, blocks: List[Dict],
                        color: str = "red", width: int = 2) -> Image.Image:
    """
    Draws rectangles around detected text lines on the image.

    Textract returns BoundingBox as relative values (0.0-1.0),
    so we multiply by the image dimensions.

    Returns:
        Copy of the image with bounding boxes drawn
    """
    img = image.copy()
    img_width, img_height = img.size
    draw = ImageDraw.Draw(img)

    for block in blocks:
        if block['BlockType'] == 'LINE':
            box = block['Geometry']['BoundingBox']
            left   = img_width  * box['Left']
            top    = img_height * box['Top']
            w      = img_width  * box['Width']
            h      = img_height * box['Height']
            draw.rectangle(
                [(left, top), (left + w, top + h)],
                outline=color,
                width=width
            )
    return img


### Main logic
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    is_pdf = uploaded_file.type == "application/pdf"

    # Prepare list of pages
    if is_pdf:
        with st.spinner("Converting PDF pages to images..."):
            pages = pdf_to_images(file_bytes)
        st.info(f"PDF loaded — {len(pages)} page(s) to process.")
    else:
        pages = [Image.open(io.BytesIO(file_bytes))]
        st.image(pages[0], caption='Uploaded Image')

    # Textract: process each page
    all_text_parts: List[str] = []
    all_blocks:     List[tuple] = []   # (PIL Image, blocks)

    with st.spinner("Processing with Amazon Textract..."):
        for i, page_img in enumerate(pages):
            # PIL Image -> PNG bytes (Textract accepts image bytes only)
            buf = io.BytesIO()
            page_img.save(buf, format="PNG")
            page_bytes = buf.getvalue()

            resp = process_document_for_qa(page_bytes)
            if resp:
                page_text = extract_text_from_response(resp)
                all_text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
                all_blocks.append((page_img, resp['Blocks']))

    if not all_text_parts:
        st.error("Textract returned no results.")
        st.stop()

    extracted_text = "\n\n".join(all_text_parts)

    # Display extracted text
    with st.expander("View Extracted Text"):
        st.code(extracted_text)

    # Bounding boxes (one per page)
    st.subheader("Bounding Box Visualization")
    for i, (page_img, blocks) in enumerate(all_blocks):
        boxed_img = draw_bounding_boxes(page_img, blocks)
        label = f"Page {i + 1} — detected text" if is_pdf else "Detected text with bounding boxes"
        st.image(boxed_img, caption=label)

    # Q&A
    st.subheader("Document Question Answering")
    question = st.text_input("Ask a question about the document content:")

    if question and extracted_text:
        with st.spinner("Searching for answer..."):
            answer = ask_bedrock_question(extracted_text, question)
            if answer:
                st.success(f"**Answer:** {answer}")
            else:
                st.warning("Could not generate an answer for this question.")
