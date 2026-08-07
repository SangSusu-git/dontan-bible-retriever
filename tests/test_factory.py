import pytest
from bible_search import factory
from bible_search.config import Settings


def _settings(**overrides):
    base = {"api_key": "test-key"}
    base.update(overrides)
    return Settings(**base)


class DummyKureEmbedder:
    def __init__(self, model_name):
        self.model_name = model_name


class DummyHfApiEmbedder:
    def __init__(self, model_name, token=None):
        self.model_name = model_name
        self.token = token


def test_make_embedder_local_returns_kure_embedder(monkeypatch):
    monkeypatch.setattr(factory, "KureEmbedder", DummyKureEmbedder)
    s = _settings(embedder="local")

    embedder = factory._make_embedder(s)

    assert isinstance(embedder, DummyKureEmbedder)
    assert embedder.model_name == s.embedding_model


def test_make_embedder_hf_returns_hf_api_embedder(monkeypatch):
    monkeypatch.setattr(factory, "HfApiEmbedder", DummyHfApiEmbedder)
    s = _settings(embedder="hf", hf_token="settings-token")

    embedder = factory._make_embedder(s)

    assert isinstance(embedder, DummyHfApiEmbedder)
    assert embedder.model_name == s.embedding_model
    assert embedder.token == "settings-token"


def test_make_embedder_invalid_value_raises():
    s = _settings(embedder="bogus")
    with pytest.raises(ValueError, match="bogus"):
        factory._make_embedder(s)
