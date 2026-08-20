#!/usr/bin/env python3
"""Download audio → transcribe (Whisper) → generate lecture notes (Claude) → save as *.md"""

import sys
import re
import logging
import whisper
import yt_dlp
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TRANSCRIPTS_DIR = Path("transcripts")
LECTURES_DIR = Path("lectures")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)
LECTURES_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename="errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

SYSTEM_PROMPT_LECTURE = """You are an expert at transforming raw conversation transcripts into
well-structured lecture notes in Markdown format.

Given a transcript, produce a comprehensive lecture document that:
- Has a clear title (H1) derived from the main topic
- Contains an **Introduction** section summarising the context
- Breaks the content into logical sections with H2/H3 headings
- Highlights key concepts, definitions, and insights using bold/italic
- Includes a **Key Takeaways** section at the end (bullet list)
- Optionally adds an **Action Items** section if any tasks were mentioned
- Uses clean, readable Markdown — no raw transcript lines, no filler phrases

Write in the same language as the transcript. Output only the Markdown document."""


# ---------------------------------------------------------------------------
# Audio download
# ---------------------------------------------------------------------------

def to_snake_case(title: str) -> str:
    title = re.sub(r"[^\w\s]", "", title)
    title = title.strip().lower()
    return re.sub(r"\s+", "_", title)


def download_audio(url: str) -> tuple[Path, str]:
    """Download audio from URL, return (audio_path, snake_case_title)."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", info["id"])
        name = to_snake_case(title)
        audio_path = Path(f"{title}.mp3")
        if not audio_path.exists():
            mp3_files = sorted(
                Path(".").glob("*.mp3"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            audio_path = mp3_files[0] if mp3_files else Path(f"{name}.mp3")
    return audio_path, name


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"


def transcribe(audio_path: Path, language: str = None) -> str:
    """Transcribe with large-v3, fallback to medium."""
    import threading
    import time

    for model_name in ["large-v3", "medium"]:
        try:
            print(f"  Loading Whisper {model_name}...")
            model = whisper.load_model(model_name)
            print(f"  Transcribing... (this may take several minutes)")

            _done = threading.Event()

            def _ticker():
                start = time.time()
                while not _done.wait(timeout=30):
                    elapsed = int(time.time() - start)
                    mins, secs = divmod(elapsed, 60)
                    print(f"  Still transcribing... {mins:02d}:{secs:02d} elapsed", flush=True)

            t = threading.Thread(target=_ticker, daemon=True)
            t.start()

            try:
                result = model.transcribe(str(audio_path), fp16=False, language=language)
            finally:
                _done.set()

            print(f"  Transcription complete ✓")
            lines = []
            for seg in result["segments"]:
                ts = format_timestamp(seg["start"])
                lines.append(f"{ts} {seg['text'].strip()}")
            return "\n".join(lines)
        except Exception as e:
            if model_name == "large-v3":
                print(f"  large-v3 failed ({e}), trying medium...")
                logging.error(f"large-v3 failed for {audio_path}: {e}")
            else:
                raise


# ---------------------------------------------------------------------------
# Lecture generation
# ---------------------------------------------------------------------------

def generate_lecture(transcript: str) -> str:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT_LECTURE,
        messages=[{"role": "user", "content": transcript}],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def already_done(name: str) -> bool:
    return (LECTURES_DIR / f"{name}.md").exists()


def run_pipeline(audio_path: Path, name: str, language: str = None, keep_audio: bool = False) -> bool:
    """Transcribe audio and generate lecture MD. Returns True on success."""
    md_out = LECTURES_DIR / f"{name}.md"

    if md_out.exists():
        print(f"  Skipping (lecture already exists): {md_out}")
        return True

    try:
        # 1. Transcribe
        print(f"  Transcribing: {name}")
        transcript = transcribe(audio_path, language)

        # Optionally persist the raw transcript for debugging / reuse
        txt_out = TRANSCRIPTS_DIR / f"{name}.txt"
        if not txt_out.exists():
            txt_out.write_text(transcript, encoding="utf-8")
            print(f"  Transcript saved: {txt_out}")

        # 2. Generate lecture
        print(f"  Generating lecture (Claude)...")
        lecture_md = generate_lecture(transcript)
        md_out.write_text(lecture_md, encoding="utf-8")
        print(f"  Lecture saved: {md_out}")

        return True

    except Exception as e:
        msg = f"Failed to process {name}: {e}"
        print(f"  ERROR: {msg}")
        logging.error(msg)
        return False

    finally:
        if not keep_audio and audio_path.exists():
            audio_path.unlink()


def process_url(url: str, language: str = None) -> bool:
    print(f"\n[URL] {url}")
    try:
        audio_path, name = download_audio(url)
        return run_pipeline(audio_path, name, language)
    except Exception as e:
        msg = f"Failed to download {url}: {e}"
        print(f"  ERROR: {msg}")
        logging.error(msg)
        return False


def process_file(path: Path, language: str = None) -> bool:
    print(f"\n[FILE] {path}")
    name = path.stem
    return run_pipeline(path, name, language, keep_audio=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    language = None

    if len(sys.argv) == 1:
        # Batch mode: read URLs from urls.txt / film-urls.txt
        urls_file = Path("urls.txt")
        if not urls_file.exists():
            urls_file = Path("film-urls.txt")
        if not urls_file.exists():
            print("No urls.txt or film-urls.txt found.")
            print("Usage: python transcribe_to_lecture.py <url|audio_file> [language]")
            sys.exit(1)

        urls = [
            u.strip()
            for u in urls_file.read_text().splitlines()
            if u.strip() and not u.startswith("#")
        ]
        print(f"Batch mode: {len(urls)} URL(s) from {urls_file}")
        ok = sum(process_url(u) for u in urls)
        print(f"\nDone: {ok}/{len(urls)} succeeded. Errors in errors.log")

    else:
        source = sys.argv[1]
        language = sys.argv[2] if len(sys.argv) > 2 else None

        if source.startswith("http"):
            process_url(source, language)
        else:
            process_file(Path(source), language)


if __name__ == "__main__":
    main()
