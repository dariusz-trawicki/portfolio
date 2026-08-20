# -*- coding: utf-8 -*-

# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "azure-ai-documentintelligence", "python-dotenv"]
# ///
"""
PROGRAM 3 of 3: field extraction with SOURCE EVIDENCE - Azure OCR.

Same pipeline as programs 1 and 2, with the OCR engine replaced: Azure
Document Intelligence instead of local Tesseract. Extraction stays rule-based
so the comparison isolates one variable - the OCR engine.

This is the point of the swappable-engine design: ocr_with_coordinates() has a
different body and an identical output contract, so grounding, hallucination
detection and drawing are untouched.

Requires in .env next to this script:
    AZURE_DI_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
    AZURE_DI_KEY=<your key>

Usage:
    uv run 03_azure_ocr.py sample.pdf
Output:
    result_azure.png / result_azure.json
    Also prints a token-level comparison against Tesseract if it is installed.
"""

import subprocess
import sys
import os
import re
import csv
import io
import json
import time
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

load_dotenv(Path(__file__).parent / ".env")

DPI = 200
MATCH_THRESHOLD = 0.80


# ===========================================================================
# PART 1a: OCR via Azure Document Intelligence.
#
# COORDINATE UNIT TRAP: Azure returns polygons in INCHES for PDF input and in
# PIXELS for image input (page.unit tells you which). We send the rendered PNG
# rather than the PDF, so the coordinates are already in the pixel space of the
# image we later draw on - no conversion, no drift.
#
# The alternative - sending the PDF and multiplying by DPI - also works and
# saves a rasterisation step, but then Azure's page geometry and our rendered
# image can disagree by a pixel or two after rounding.
# ===========================================================================
def ocr_with_coordinates_azure(image_path):
    """Return words with pixel coordinates. Same contract as the Tesseract version."""
    endpoint = os.getenv("AZURE_DI_ENDPOINT")
    key = os.getenv("AZURE_DI_KEY")
    if not endpoint or not key:
        raise RuntimeError(
            "AZURE_DI_ENDPOINT / AZURE_DI_KEY not found. Create a .env file "
            "next to this script:\n    cp .env.example .env\n"
            "Endpoint and key are in the Azure portal, under your Document "
            "Intelligence resource -> Keys and Endpoint."
        )

    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    with open(image_path, "rb") as f:
        data = f.read()

    # "prebuilt-read" is the plain OCR model - cheapest of the family.
    # "prebuilt-layout" adds tables and structure at roughly 6x the price;
    # it is the right choice once tables matter, which they do not here.
    poller = client.begin_analyze_document(
        "prebuilt-read",
        AnalyzeDocumentRequest(bytes_source=data),
        content_type="application/octet-stream",
    )
    result = poller.result()

    words = []
    for page in result.pages:
        # Guard against the unit trap rather than assuming.
        if page.unit not in ("pixel", None):
            raise RuntimeError(
                f"Unexpected coordinate unit: {page.unit}. This program expects "
                "image input (pixels). Sending a PDF returns inches and every "
                "box would land in the top-left corner."
            )

        for word in page.words or []:
            # polygon is a flat list [x1,y1, x2,y2, x3,y3, x4,y4] - four corners
            # clockwise. The text may be rotated, so take the extremes rather
            # than assuming corner 0 is top-left.
            poly = word.polygon
            xs = poly[0::2]
            ys = poly[1::2]

            words.append({
                "text": word.content,
                "x": int(min(xs)),
                "y": int(min(ys)),
                "w": int(max(xs) - min(xs)),
                "h": int(max(ys) - min(ys)),
                # Azure gives 0-1, Tesseract gives 0-100. Normalising here keeps
                # any downstream confidence threshold meaningful across engines.
                "confidence": word.confidence * 100,
            })
    return words


# ===========================================================================
# PART 1b: OCR via Tesseract - kept for side-by-side comparison.
# ===========================================================================
def ocr_with_coordinates_tesseract(image_path, lang="pol"):
    result = subprocess.run(
        ["tesseract", image_path, "-", "-l", lang, "tsv"],
        capture_output=True, text=True,
    )
    words = []
    reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text or float(row.get("conf", -1)) < 0:
            continue
        words.append({
            "text": text,
            "x": int(row["left"]), "y": int(row["top"]),
            "w": int(row["width"]), "h": int(row["height"]),
            "confidence": float(row["conf"]),
        })
    return words


# ===========================================================================
# PART 2: Field extraction - rules, identical to program 1.
# ===========================================================================
RULES = {
    "case_number": r"[IVX]+\s*[A-Z]{1,3}\s*\d+/\d{2,4}",
    "amount":      r"\d{1,3}(?:\s\d{3})*,\d{2}\s*zł",
    "date":        r"\d{1,2}\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca"
                   r"|sierpnia|września|października|listopada|grudnia)\s+\d{4}",
    "tax_id":      r"\d{3}-\d{2}-\d{2}-\d{3}",
    "invoice_no":  r"(?:FS/|nr\s+)\d+[/\d]*",
}


def extract_fields(text):
    found = []
    for name, pattern in RULES.items():
        for match in re.finditer(pattern, text):
            value = match.group().strip()
            found.append({"field": name, "value": value, "quote": value})
    return found


# ===========================================================================
# PART 3: Grounding - identical to programs 1 and 2.
# ===========================================================================
def _squash(s):
    return re.sub(r"\s+", "", s).lower()


def locate_on_page(quote, words, threshold=MATCH_THRESHOLD):
    target = _squash(quote)
    count = len(quote.split())
    best_score, best_window = 0.0, None

    for length in range(max(1, count - 1), count + 3):
        for start in range(len(words) - length + 1):
            window = words[start:start + length]
            candidate = _squash(" ".join(w["text"] for w in window))
            score = SequenceMatcher(None, target, candidate).ratio()
            if score > best_score:
                best_score, best_window = score, window

    if best_score < threshold or not best_window:
        return None, best_score

    return (min(w["x"] for w in best_window),
            min(w["y"] for w in best_window),
            max(w["x"] + w["w"] for w in best_window),
            max(w["y"] + w["h"] for w in best_window)), best_score


# ===========================================================================
# PART 4: Drawing - identical to programs 1 and 2.
# ===========================================================================
COLORS = {
    "case_number": (200, 30, 30), "amount": (20, 110, 200), "date": (20, 140, 60),
    "tax_id": (150, 60, 170), "invoice_no": (200, 120, 0),
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _load_font(size=15):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_evidence(image_path, fields, output_path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = _load_font()
    for field in fields:
        if not field.get("bbox"):
            continue
        x1, y1, x2, y2 = field["bbox"]
        color = COLORS.get(field["field"], (0, 0, 0))
        draw.rectangle([x1 - 3, y1 - 3, x2 + 3, y2 + 3], outline=color, width=3)
        label = field["field"]
        tw = draw.textlength(label, font=font)
        draw.rectangle([x1 - 3, y1 - 24, x1 + tw + 9, y1 - 4], fill=color)
        draw.text((x1 + 2, y1 - 22), label, fill=(255, 255, 255), font=font)
    image.save(output_path)


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: uv run 03_azure_ocr.py <file.pdf>")
        return

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(f"File not found: {pdf}")
        return

    os.makedirs("work", exist_ok=True)
    subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-f", "1", "-l", "1",
                    pdf, "work/page"], check=True)
    image_path = os.path.join(
        "work", sorted(f for f in os.listdir("work") if f.endswith(".png"))[0])

    # STEP 1 - OCR via Azure, timed (latency is a real cost of cloud OCR)
    print("Sending page to Azure Document Intelligence...")
    started = time.perf_counter()
    words = ocr_with_coordinates_azure(image_path)
    elapsed = time.perf_counter() - started
    mean_conf = sum(w["confidence"] for w in words) / max(len(words), 1)
    print(f"Azure read {len(words)} words in {elapsed:.1f}s "
          f"(mean confidence {mean_conf:.1f}%).")

    # Side-by-side with the local engine, if available
    try:
        t0 = time.perf_counter()
        tess = ocr_with_coordinates_tesseract(image_path)
        t_elapsed = time.perf_counter() - t0
        t_conf = sum(w["confidence"] for w in tess) / max(len(tess), 1)
        print(f"Tesseract read {len(tess)} words in {t_elapsed:.1f}s "
              f"(mean confidence {t_conf:.1f}%).")
    except FileNotFoundError:
        print("Tesseract not installed - skipping comparison.")

    full_text = " ".join(w["text"] for w in words)

    # STEP 2 - extraction
    fields = extract_fields(full_text)
    print(f"\nFound {len(fields)} candidate fields.\n")

    # STEP 3 - grounding
    grounded = 0
    for field in fields:
        bbox, score = locate_on_page(field["quote"], words)
        field["bbox"] = bbox
        field["match_score"] = round(score, 3)
        if bbox:
            grounded += 1
            status = f"OK      ({score:.2f})"
        else:
            status = f"MISSING ({score:.2f}) <- review queue"
        print(f"  {field['field']:<14}{field['value']:<28}{status}")

    print(f"\nGrounded {grounded} of {len(fields)} fields.")

    # STEP 4 - evidence
    draw_evidence(image_path, fields, "result_azure.png")
    with open("result_azure.json", "w", encoding="utf-8") as f:
        json.dump(fields, f, ensure_ascii=False, indent=2)
    print("Wrote: result_azure.png and result_azure.json")


main()
