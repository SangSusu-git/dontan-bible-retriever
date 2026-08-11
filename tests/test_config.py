from bible_search.config import Settings

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "secret123")
    s = Settings()
    assert s.api_key == "secret123"
    assert s.dense_threshold == 0.7
    assert s.chroma_collection == "verses"
    assert s.bm25_top_k == 100
    assert s.embedder == "local"
    assert s.hf_token is None
    assert s.vector_store == "chroma"
    assert s.numpy_index_path == "numpy_index"
    assert s.numpy_index_dim is None
    assert s.use_token_cache is False
    assert s.token_cache_path == "token_cache.json"
    assert s.tokenizer == "kiwi"
    assert s.fusion == "weighted"
    assert s.bm25_b == 0.4
    assert s.w_bm25 == 0.7
    assert s.w_dense == 1.0
    assert s.w_cov == 2.0
    assert s.w_prox == 0.5
    assert s.rrf_k == 60
    assert s.max_results == 50

def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "k")
    monkeypatch.setenv("BIBLE_DENSE_THRESHOLD", "0.9")
    s = Settings()
    assert s.dense_threshold == 0.9

def test_settings_ranking_env_overrides(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "k")
    monkeypatch.setenv("BIBLE_FUSION", "rrf")
    monkeypatch.setenv("BIBLE_BM25_B", "0.0")
    monkeypatch.setenv("BIBLE_W_BM25", "1.0")
    monkeypatch.setenv("BIBLE_W_DENSE", "0.5")
    monkeypatch.setenv("BIBLE_W_COV", "1.5")
    monkeypatch.setenv("BIBLE_W_PROX", "0.25")
    s = Settings()
    assert s.fusion == "rrf"
    assert s.bm25_b == 0.0
    assert s.w_bm25 == 1.0
    assert s.w_dense == 0.5
    assert s.w_cov == 1.5
    assert s.w_prox == 0.25
