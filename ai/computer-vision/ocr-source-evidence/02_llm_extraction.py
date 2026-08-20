# -*- coding: utf-8 -*-

# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "anthropic", "python-dotenv"]
# ///
"""
PROGRAM 2 of 3: field extraction with SOURCE EVIDENCE - model-based.

Same pipeline as 01_regex_extraction.py, with one part replaced: fields are
extracted by a language model instead of regular expressions. Everything
downstream - grounding, hallucination detection, drawing - is unchanged,
which is the point being demonstrated.

The two programs are standalone by design: neither imports the other, so
each can be read top to bottom without jumping between files. The shared
OCR/grounding/drawing code is duplicated on purpose for that reason. In a
real codebase it would live in one module.

Requires an API key in a .env file next to this script:
    ANTHROPIC_API_KEY=sk-ant-...

Usage:
    uv run 02_llm_extraction.py sample.pdf
Output:
    result_llm.png    - page with highlighted fields
    result_llm.json   - extracted data with quotes, boxes and match scores
"""

import subprocess
import sys
import os
import re
import json
import csv
import io
from difflib import SequenceMatcher
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Load .env from the script's own directory, not the current working
# directory. Without the explicit path, running from elsewhere silently
# fails to find the key and the error looks like an API problem.
load_dotenv(Path(__file__).parent / ".env")

DPI = 200
OCR_LANG = "pol"
MATCH_THRESHOLD = 0.80
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ===========================================================================
# PART 1: OCR that returns WORDS WITH COORDINATES, not flat text.
# Identical to program 1 - the OCR layer does not care what consumes it.
# ===========================================================================
def ocr_with_coordinates(image_path, lang=OCR_LANG):
    result = subprocess.run(
        ["tesseract", image_path, "-", "-l", lang, "tsv"],
        capture_output=True, text=True,
    )

    words = []
    reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        if float(row.get("conf", -1)) < 0:
            continue
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
# PART 2: Field extraction by a language model.
#
# This is the ONLY part that differs from program 1. The output contract is
# identical: a list of {field, value, quote} records.
# ===========================================================================
SCHEMA = {
    "case_number":   "case file reference, e.g. 'I C 1284/23'",
    "judgment_date": "date the judgment was issued",
    "principal_sum": "principal amount awarded (not the costs of proceedings)",
    "costs_sum":     "costs of proceedings awarded",
    "tax_id":        "tax identification number (NIP), if present",
    "invoice_no":    "invoice number, if present",
}


def _build_prompt(document_text):
    field_list = "\n".join(f"- {k}: {v}" for k, v in SCHEMA.items())
    return f"""Extract the following fields from this official court document.
The document is in Polish; field names below are in English.

Fields:
{field_list}

RULES - follow these strictly:
1. For every field return a "value" and a "quote".
2. The "quote" must be a VERBATIM span copied character for character from
   the document text, including any OCR errors it contains. The quote is used
   to locate the field on the scanned page, so any correction makes it
   useless.
3. Keep quotes short - 2 to 8 words covering the value itself.
4. If a field is NOT present, set "value": null and omit the quote. Do not
   guess and do not infer from context.
5. Do NOT return coordinates or page numbers of any kind. Position is
   resolved by a separate mechanism from the quote.

Reply with a JSON object ONLY - no commentary, no ``` fences:
{{"case_number": {{"value": "...", "quote": "..."}}, ...}}

Document:
---
{document_text}
---"""


def extract_fields_llm(text, model=MODEL):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found. Create a .env file next to this "
            "script:\n    cp .env.example .env\nand put your key in it."
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        # Zero temperature: randomness only hurts factual extraction, and it
        # makes the same document yield different results across runs, which
        # would make evaluation meaningless.
        temperature=0,
        messages=[{"role": "user", "content": _build_prompt(text)}],
    )

    raw = response.content[0].text.strip()
    # Models asked for bare JSON still wrap it in fences sometimes. Cheaper to
    # handle here than to fight it in the prompt.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Model did not return valid JSON. Received:")
        print(raw[:400])
        return []

    found = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        value, quote = entry.get("value"), entry.get("quote")

        # null means "not in the document" - a correct answer, not a failure.
        # Without permitting null the model invents something to fill the schema.
        if value is None:
            continue
        # A value with no quote cannot be verified, so it is dropped for the
        # same reason an unmatchable quote is dropped later.
        if not quote:
            print(f"  [skipped] {name}: model gave a value with no quote")
            continue

        found.append({"field": name, "value": str(value), "quote": str(quote)})
    return found


# ===========================================================================
# PART 3: GROUNDING - identical to program 1.
# ===========================================================================
def _squash(s):
    return re.sub(r"\s+", "", s).lower()


def locate_on_page(quote, words, threshold=MATCH_THRESHOLD):
    """Return (bounding_box, score). Box is None when the quote is not found -
    that is the hallucination signal."""
    target = _squash(quote)
    quote_word_count = len(quote.split())

    best_score, best_window = 0.0, None
    for length in range(max(1, quote_word_count - 1), quote_word_count + 3):
        for start in range(len(words) - length + 1):
            window = words[start:start + length]
            candidate = _squash(" ".join(w["text"] for w in window))
            score = SequenceMatcher(None, target, candidate).ratio()
            if score > best_score:
                best_score, best_window = score, window

    if best_score < threshold or not best_window:
        return None, best_score

    x1 = min(w["x"] for w in best_window)
    y1 = min(w["y"] for w in best_window)
    x2 = max(w["x"] + w["w"] for w in best_window)
    y2 = max(w["y"] + w["h"] for w in best_window)
    return (x1, y1, x2, y2), best_score


# ===========================================================================
# PART 4: Draw the evidence - identical to program 1.
# ===========================================================================
COLORS = {
    "case_number": (200, 30, 30), "principal_sum": (20, 110, 200),
    "costs_sum": (20, 110, 200), "judgment_date": (20, 140, 60),
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
        print("Usage: uv run 02_llm_extraction.py <file.pdf>")
        return

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(f"File not found: {pdf}")
        print(f"Current directory: {os.getcwd()}")
        print("PDFs here:", [f for f in os.listdir(".") if f.endswith(".pdf")] or "none")
        return

    os.makedirs("work", exist_ok=True)
    subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-f", "1", "-l", "1",
                    pdf, "work/page"], check=True)
    image_path = os.path.join(
        "work", sorted(f for f in os.listdir("work") if f.endswith(".png"))[0])

    # STEP 1 - OCR with coordinates
    words = ocr_with_coordinates(image_path)
    print(f"OCR read {len(words)} words (each with its position on the page).")
    full_text = " ".join(w["text"] for w in words)

    # STEP 2 - extraction by model
    print(f"Asking {MODEL} to extract fields...")
    fields = extract_fields_llm(full_text)
    print(f"Model returned {len(fields)} fields.\n")

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
        print(f"  {field['field']:<16}{field['value']:<26}{status}")
        print(f"  {'':16}quote: {field['quote']!r}")

    print(f"\nGrounded {grounded} of {len(fields)} fields.")
    if grounded < len(fields):
        print("Unmatched quotes are either hallucinated or badly OCR'd - "
              "neither is safe to auto-approve.")

    # STEP 4 - visual evidence
    draw_evidence(image_path, fields, "result_llm.png")
    with open("result_llm.json", "w", encoding="utf-8") as f:
        json.dump(fields, f, ensure_ascii=False, indent=2)
    print("Wrote: result_llm.png and result_llm.json")


main()
