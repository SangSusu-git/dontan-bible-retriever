from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIBLE_", env_file=".env")

    api_key: str
    data_path: str = "data/verses.jsonl"
    chroma_path: str = "chroma"
    chroma_collection: str = "verses"
    embedding_model: str = "nlpai-lab/KURE-v1"
    embedder: str = "local"
    hf_token: str | None = None
    vector_store: str = "chroma"
    numpy_index_path: str = "numpy_index"
    numpy_index_dim: int | None = None
    dense_threshold: float = 0.7
    rrf_k: int = 60
    max_results: int = 50
    bm25_top_k: int = 30
    token_cache_path: str = "token_cache.json"
    use_token_cache: bool = False
    tokenizer: str = "kiwi"


@lru_cache
def get_settings() -> Settings:
    return Settings()
