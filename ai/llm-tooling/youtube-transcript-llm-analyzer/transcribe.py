#!/usr/bin/env python3
"""Transcription script using Whisper large-v3 with batch processing."""

import sys
import re
import logging
import whisper
import yt_dlp
from pathlib import Path

TRANSCRIPTS_DIR = Path("transcripts")
ANALYSIS_DIR = Path("analysis")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)
ANALYSIS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename="errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


def to_snake_case(title: str) -> str:
    title = re.sub(r"[^\w\s]", "", title)
    title = title.strip().lower()
    return re.sub(r"\s+", "_", title)


def download_audio(url: str) -> tuple[Path, str]:
    """Download audio, return (audio_path, snake_case_title)."""
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
        # yt-dlp saves with original title, find the file
        audio_path = Path(f"{title}.mp3")
        if not audio_path.exists():
            # fallback: search for downloaded mp3
            mp3_files = sorted(Path(".").glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
            audio_path = mp3_files[0] if mp3_files else Path(f"{name}.mp3")
    return audio_path, name


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"


def transcribe(audio_path: Path, language: str = None) -> str:
    """Transcribe with large-v3, fallback to medium."""
    for model_name in ["large-v3", "medium"]:
        try:
            print(f"  Loading Whisper {model_name}...")
            model = whisper.load_model(model_name)
            result = model.transcribe(str(audio_path), fp16=False, language=language)
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


def already_processed(name: str) -> bool:
    return (TRANSCRIPTS_DIR / f"{name}.txt").exists()


def process_url(url: str) -> bool:
    """Process single URL. Returns True on success."""
    print(f"\n[URL] {url}")
    try:
        audio_path, name = download_audio(url)
        if already_processed(name):
            print(f"  Skipping (already processed): {name}")
            if audio_path.exists():
                audio_path.unlink()
            return True
        print(f"  Transcribing: {name}")
        transcript = transcribe(audio_path)
        out = TRANSCRIPTS_DIR / f"{name}.txt"
        out.write_text(transcript, encoding="utf-8")
        print(f"  Saved: {out}")
        if audio_path.exists():
            audio_path.unlink()
        return True
    except Exception as e:
        msg = f"Failed to process {url}: {e}"
        print(f"  ERROR: {msg}")
        logging.error(msg)
        return False


def main():
    if len(sys.argv) == 1:
        # Batch mode: read from urls.txt
        urls_file = Path("urls.txt")
        if not urls_file.exists():
            urls_file = Path("film-urls.txt")
        if not urls_file.exists():
            print("No urls.txt or film-urls.txt found. Usage: uv run transcribe.py <url>")
            sys.exit(1)
        urls = [u.strip() for u in urls_file.read_text().splitlines() if u.strip() and not u.startswith("#")]
        print(f"Batch mode: {len(urls)} URL(s) from {urls_file}")
        ok = sum(process_url(u) for u in urls)
        print(f"\nDone: {ok}/{len(urls)} succeeded. Errors in errors.log")
    else:
        source = sys.argv[1]
        language = sys.argv[2] if len(sys.argv) > 2 else None
        if source.startswith("http"):
            process_url(source)
        else:
            audio_path = Path(source)
            name = audio_path.stem
            transcript = transcribe(audio_path, language)
            out = TRANSCRIPTS_DIR / f"{name}.txt"
            out.write_text(transcript, encoding="utf-8")
            print(f"Saved: {out}")


if __name__ == "__main__":
    main()
