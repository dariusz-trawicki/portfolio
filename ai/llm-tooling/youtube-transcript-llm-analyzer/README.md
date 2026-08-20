# Transcriptions

Local audio/video transcription from YouTube using Whisper, with optional LLM analysis.

## Stack

- Python 3.11+ / [uv](https://docs.astral.sh/uv/)
- [Whisper large-v3](https://github.com/openai/whisper) — local transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — audio download from YouTube
- [Anthropic API](https://www.anthropic.com/) — transcript analysis (sentiment, topics)
- ffmpeg (system dependency)

## Installation

```bash
uv sync
```

System requirement: `ffmpeg` must be available in PATH.

Create a `.env` file with your API key for analysis:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Structure

```
├── transcribe.py     # transcription script
├── analyze.py        # LLM analysis script
├── film-urls.txt     # URL list for batch processing
├── transcripts/      # transcription results (.txt with timestamps)
├── analysis/         # analysis results (.json)
└── errors.log        # errors
```

## Transcription

### Single YouTube URL

```bash
uv run transcribe.py https://youtube.com/watch?v=...
```

With explicit language:

```bash
uv run transcribe.py https://youtube.com/watch?v=... pl
```

### Local audio file

```bash
uv run transcribe.py file.mp3
uv run transcribe.py file.mp3 pl
```

### Batch (multiple videos)

Add URLs to `film-urls.txt` (one per line, `#` = comment):

```
https://youtube.com/watch?v=AAA
https://youtube.com/watch?v=BBB
# skip this one
# https://youtube.com/watch?v=CCC
```

Run:

```bash
uv run transcribe.py
```

Files already present in `transcripts/` are skipped.

### Output format

Transcript saved to `transcripts/<title_snake_case>.txt`:

```
[00:00] Welcome to today's episode...
[00:15] Today we will cover...
```

## LLM Analysis

Analysis requires `ANTHROPIC_API_KEY` in `.env`.

### Single file

```bash
uv run analyze.py transcripts/file_name.txt
```

### Batch (all unprocessed transcripts)

```bash
uv run analyze.py
```

### Output format

Result saved to `analysis/<name>.json`:

```json
{
  "sentiment": "positive",
  "key_topics": ["topic1", "topic2"],
  "action_items": ["action1"],
  "lead_score": 7
}
```


## Lecture notes generator
- Pipeline:
```
Download audio → transcribe (Whisper) → generate lecture notes (Claude) → save as *.md
```

```bash
# Single video:
uv run transcribe_to_lecture.py https://youtube.com/...

# Local MP3 file
uv run transcribe_to_lecture.py audio.mp3

# Batch (multiple videos) - add URLs to `film-urls.txt`
uv run transcribe_to_lecture.py
```

## Notes

- Whisper runs with `fp16=False` (Apple Silicon compatibility)
- Language is auto-detected unless specified explicitly
- If `large-v3` fails, automatically falls back to `medium`
- Errors are logged to `errors.log`, processing continues
