from pydantic_settings import BaseSettings
from pathlib import Path

ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_access_key: str
    inference_base_url: str = "https://inference.do-ai.run/v1"
    model: str = "anthropic-claude-4.6-sonnet"
    synergy_model: str = "anthropic-claude-3.5-haiku"

    # CV
    entities_model_path: Path = ROOT / "models" / "entities.onnx"
    ui_model_path: Path = ROOT / "models" / "ui.onnx"
    cv_confidence_threshold: float = 0.6  # below this → ask user to clarify

    # RAG
    chroma_persist_dir: Path = ROOT / "data" / "chroma"
    embed_model: str = "all-MiniLM-L6-v2"
    retrieval_top_k: int = 6  # 3 card-level + 3 guide-level

    # LLM
    max_output_tokens: int = 1024
    stream: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
