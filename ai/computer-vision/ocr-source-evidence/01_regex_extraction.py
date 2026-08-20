# -*- coding: utf-8 -*-

# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""
PROGRAM 1 of 3: field extraction with SOURCE EVIDENCE - rule-based.

Extraction here uses regular expressions. No API key, no cost, no network.
Program 2 (02_llm_extraction.py) does the same job with a language model.
Both are standalone: neither imports the other.

The idea:
    Never ask the model for coordinates - it hallucinates them.
    The extractor (here: regex rules, in production: an LLM) returns a
    VALUE and a VERBATIM QUOTE. The quote is matched against the words
    the OCR engine read - and OCR knows where every word sits on the page.
    The bounding box comes from there.

The side effect matters more than the main effect:
    If the quote CANNOT be located on the page, it was either hallucinated
    or the OCR mangled it beyond recognition. Either way the value is not
    safe to auto-approve. We get a hallucination detector for free.

Usage:
    uv run 01_regex_extraction.py sample.pdf
Output:
    result_regex.png      - page with highlighted fields
    result_regex.json     - extracted data with boxes and match scores
"""

import subprocess
import sys
import os
import re
import json
import csv
import io
from difflib import SequenceMatcher
from PIL import Image, ImageDraw, ImageFont

DPI = 200
LANG = "pol"          # Tesseract language model; documents here are Polish
MATCH_THRESHOLD = 0.80


# ===========================================================================
# PART 1: OCR that returns WORDS WITH COORDINATES, not flat text.
#
# This is the key architectural decision. A plain string loses page geometry
# permanently, which makes source evidence impossible to reconstruct later.
# ===========================================================================
def ocr_with_coordinates(image_path, lang=LANG):
    """Return a list of words. Each word carries its text and its box."""

    # Tesseract's "tsv" output mode emits one row per recognised word,
    # with left/top/width/height columns.
    result = subprocess.run(
        ["tesseract", image_path, "-", "-l", lang, "tsv"],
        capture_output=True, text=True,
    )

    words = []
    # QUOTE_NONE matters: official documents are full of quotation marks,
    # and the default CSV parser would treat them as field delimiters
    # and merge columns together.
    reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue                        # blank rows are spacing
        if float(row.get("conf", -1)) < 0:
            continue                        # conf = -1 marks structural rows
                                            # (blocks, paragraphs, lines)

        words.append({
            "text": text,
            "x": int(row["left"]),
            "y": int(row["top"]),
            "w": int(row["width"]),
            "h": int(row["height"]),
            "confidence": float(row["conf"]),
        })
    return words


# ===========================================================================
# PART 2: Field extraction.
#
# Deliberately regex-based so the demo runs with no API key and no cost.
# In production an LLM with a JSON Schema sits here instead - and nothing
# downstream changes, because the model also returns only value + quote.
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
    """Return found fields. Each carries a name, a value and a quote."""
    found = []
    for name, pattern in RULES.items():
        for match in re.finditer(pattern, text):
            found.append({
                "field": name,
                "value": match.group().strip(),
                # The quote is what gets located on the page. With an LLM
                # this is the verbatim span the model claims to have read.
                "quote": match.group().strip(),
            })
    return found


# ===========================================================================
# PART 3: GROUNDING - the core of the demo.
#
# We have a quote (text) and words with coordinates. Slide a window across
# the words and find where the quote fits best.
# ===========================================================================
def _squash(s):
    """Strip whitespace and lowercase, for comparison only."""
    return re.sub(r"\s+", "", s).lower()


def locate_on_page(quote, words, threshold=MATCH_THRESHOLD):
    """
    Return (bounding_box, match_score). Box is None when the quote could
    not be located - that is the hallucination signal.
    """
    target = _squash(quote)
    quote_word_count = len(quote.split())

    best_score = 0.0
    best_window = None

    # Window lengths vary by +/- a couple of words because OCR sometimes
    # merges or splits tokens.
    for length in range(max(1, quote_word_count - 1), quote_word_count + 3):
        for start in range(len(words) - length + 1):
            window = words[start:start + length]
            candidate = _squash(" ".join(w["text"] for w in window))

            score = SequenceMatcher(None, target, candidate).ratio()
            if score > best_score:
                best_score = score
                best_window = window

    if best_score < threshold or not best_window:
        return None, best_score

    x1 = min(w["x"] for w in best_window)
    y1 = min(w["y"] for w in best_window)
    x2 = max(w["x"] + w["w"] for w in best_window)
    y2 = max(w["y"] + w["h"] for w in best_window)

    return (x1, y1, x2, y2), best_score


# ===========================================================================
# PART 4: Draw the evidence.
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
        text_width = draw.textlength(label, font=font)
        draw.rectangle([x1 - 3, y1 - 24, x1 + text_width + 9, y1 - 4], fill=color)
        draw.text((x1 + 2, y1 - 22), label, fill=(255, 255, 255), font=font)

    image.save(output_path)


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: uv run 01_regex_extraction.py <file.pdf>")
        return

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(f"File not found: {pdf}")
        print(f"Current directory: {os.getcwd()}")
        pdfs = [f for f in os.listdir(".") if f.endswith(".pdf")]
        print("PDFs here:", pdfs or "none")
        return

    os.makedirs("work", exist_ok=True)

    # PDF -> image, because OCR reads images, not PDFs. First page only.
    subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-f", "1", "-l", "1",
                    pdf, "work/page"], check=True)
    pages = sorted(f for f in os.listdir("work") if f.endswith(".png"))
    image_path = os.path.join("work", pages[0])

    # STEP 1 - OCR with coordinates
    words = ocr_with_coordinates(image_path)
    print(f"OCR read {len(words)} words (each with its position on the page).")

    full_text = " ".join(w["text"] for w in words)

    # STEP 2 - field extraction
    fields = extract_fields(full_text)
    print(f"Found {len(fields)} candidate fields.\n")

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

    # STEP 4 - visual evidence
    draw_evidence(image_path, fields, "result_regex.png")
    with open("result_regex.json", "w", encoding="utf-8") as f:
        json.dump(fields, f, ensure_ascii=False, indent=2)

    print("Wrote: result_regex.png and result_regex.json")


main()
