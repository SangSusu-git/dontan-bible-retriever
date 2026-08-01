from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIBLE_", env_file=".env")

    api_key: str
    data_path: str = "data/verses.jsonl"
    chroma_path: str = "chroma"
    chroma_collection: str = "verses"
    embedding_model: str = "nlpai-lab/KURE-v1"
    dense_threshold: float = 0.8
    rrf_k: int = 60
    max_results: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
