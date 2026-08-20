#!/usr/bin/env python3
"""LLM analysis of transcripts → JSON output (sentiment, topics, action_items, lead_score)."""

import sys
import json
import logging
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TRANSCRIPTS_DIR = Path("transcripts")
ANALYSIS_DIR = Path("analysis")
ANALYSIS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename="errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

SYSTEM_PROMPT = """Analyze the transcript and respond ONLY with a valid JSON object:
{
  "sentiment": "positive" | "neutral" | "negative",
  "key_topics": ["topic1", "topic2", ...],
  "action_items": ["action1", "action2", ...],
  "lead_score": <integer 1-10>
}
No explanation, no markdown — pure JSON only."""


def analyze(transcript: str) -> dict:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def process_transcript(txt_path: Path) -> bool:
    out_path = ANALYSIS_DIR / txt_path.with_suffix(".json").name
    if out_path.exists():
        print(f"  Skipping (already analyzed): {txt_path.name}")
        return True
    try:
        print(f"  Analyzing: {txt_path.name}")
        transcript = txt_path.read_text(encoding="utf-8")
        result = analyze(transcript)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved: {out_path}")
        return True
    except Exception as e:
        msg = f"Failed to analyze {txt_path}: {e}"
        print(f"  ERROR: {msg}")
        logging.error(msg)
        return False


def main():
    if len(sys.argv) == 1:
        # Batch: analyze all unprocessed transcripts
        txts = sorted(TRANSCRIPTS_DIR.glob("*.txt"))
        if not txts:
            print("No transcripts found in transcripts/")
            sys.exit(1)
        print(f"Batch mode: {len(txts)} transcript(s)")
        ok = sum(process_transcript(p) for p in txts)
        print(f"\nDone: {ok}/{len(txts)} succeeded.")
    else:
        path = Path(sys.argv[1])
        if not path.exists():
            path = TRANSCRIPTS_DIR / sys.argv[1]
        process_transcript(path)


if __name__ == "__main__":
    main()
