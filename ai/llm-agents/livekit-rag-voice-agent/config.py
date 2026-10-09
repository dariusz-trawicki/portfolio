"""Application settings, loaded from environment variables / a `.env` file."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Company -----------------------------------------------------------
    company_name: str = "Kestrel Energy"

    # --- LiveKit (only needed by the voice agent) --------------------------
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # --- LLM ---------------------------------------------------------------
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.1

    # --- Knowledge base (RAG) ----------------------------------------------
    docs_dir: str = "docs"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Embedded (on-disk) Qdrant by default; set QDRANT_URL to use a server.
    qdrant_path: str = "./data/qdrant"
    qdrant_url: str = ""
    collection_name: str = "kestrel_knowledge"
    retrieval_top_k: int = 4
    retrieval_min_score: float = 0.45

    # --- Voice -------------------------------------------------------------
    stt_model: str = "deepgram/nova-3"
    stt_language: str = "en"
    tts_model: str = "inworld/inworld-tts-2"
    tts_voice: str = "Olivia"
    tts_language: str = "en"
    endpointing_min_delay: float = 0.5
    endpointing_max_delay: float = 5.0


settings = Settings()


def export_provider_env() -> None:
    """Expose credentials under the variable names the LiveKit and Groq SDKs
    read. Empty values are skipped so they never mask real ones."""
    for name, value in {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
        "GROQ_API_KEY": settings.groq_api_key,
    }.items():
        if value:
            os.environ.setdefault(name, value)


export_provider_env()
