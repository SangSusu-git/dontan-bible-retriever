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
    bm25_top_k: int = 100
    token_cache_path: str = "token_cache.json"
    use_token_cache: bool = False
    tokenizer: str = "kiwi"
    # 실험(scripts/experiment_ranking.py, config C8)으로 검증된 랭킹 기본값.
    # 183개 평가 질의 MRR 0.674→0.928, 284개 강건성 세트에서 회귀 0건/개선 30건.
    fusion: str = "weighted"  # "weighted" | "rrf"
    bm25_b: float = 0.4
    w_bm25: float = 0.7
    w_dense: float = 1.0
    w_cov: float = 2.0
    w_prox: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
