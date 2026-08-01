from bible_search.config import Settings

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "secret123")
    s = Settings()
    assert s.api_key == "secret123"
    assert s.dense_threshold == 0.8
    assert s.chroma_collection == "verses"

def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "k")
    monkeypatch.setenv("BIBLE_DENSE_THRESHOLD", "0.9")
    s = Settings()
    assert s.dense_threshold == 0.9
