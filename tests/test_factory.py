import numpy as np
import pytest
from bible_search import factory
from bible_search.config import Settings
from bible_search.retrievers.dense import DenseRetriever
from bible_search.vectorstore import NumpyDenseRetriever


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


def test_make_dense_retriever_numpy_selects_numpy_retriever(monkeypatch, verses, fake_embedder):
    fake_vectors = np.zeros((len(verses), 8), dtype=np.float32)
    fake_ids = [v.id for v in verses]
    monkeypatch.setattr(
        factory, "load_numpy_index",
        lambda path: (fake_vectors, fake_ids),
    )
    s = _settings(vector_store="numpy", numpy_index_path="unused-path")

    retriever = factory._make_dense_retriever(s, verses, fake_embedder)

    assert isinstance(retriever, NumpyDenseRetriever)


def test_make_dense_retriever_chroma_selects_chroma_retriever(monkeypatch, verses, fake_embedder):
    class DummyCollection:
        pass

    class DummyClient:
        def __init__(self, path):
            self.path = path

        def get_collection(self, name):
            return DummyCollection()

    monkeypatch.setattr(factory.chromadb, "PersistentClient", DummyClient)
    s = _settings(vector_store="chroma")

    retriever = factory._make_dense_retriever(s, verses, fake_embedder)

    assert isinstance(retriever, DenseRetriever)


def test_make_dense_retriever_invalid_value_raises(verses, fake_embedder):
    s = _settings(vector_store="bogus")
    with pytest.raises(ValueError, match="bogus"):
        factory._make_dense_retriever(s, verses, fake_embedder)
