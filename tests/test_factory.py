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
        lambda path: (fake_vectors, fake_ids, None),
    )
    s = _settings(vector_store="numpy", numpy_index_path="unused-path")

    retriever = factory._make_dense_retriever(s, verses, fake_embedder)

    assert isinstance(retriever, NumpyDenseRetriever)


def test_make_dense_retriever_numpy_passes_basis(monkeypatch, verses, fake_embedder):
    fake_vectors = np.zeros((len(verses), 4), dtype=np.float32)
    fake_ids = [v.id for v in verses]
    fake_basis = np.zeros((4, 8), dtype=np.float32)
    monkeypatch.setattr(
        factory, "load_numpy_index",
        lambda path: (fake_vectors, fake_ids, fake_basis),
    )
    s = _settings(vector_store="numpy", numpy_index_path="unused-path")

    retriever = factory._make_dense_retriever(s, verses, fake_embedder)

    assert isinstance(retriever, NumpyDenseRetriever)
    assert retriever._basis is fake_basis


def test_make_dense_retriever_chroma_selects_chroma_retriever(monkeypatch, verses, fake_embedder):
    class DummyCollection:
        pass

    class DummyClient:
        def __init__(self, path):
            self.path = path

        def get_collection(self, name):
            return DummyCollection()

    # factory는 chromadb를 함수 안에서 지연 import한다(경량 배포에서는 미설치).
    # 따라서 factory 모듈 속성이 아니라 chromadb 모듈 자체에 패치해야 한다.
    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", DummyClient)
    s = _settings(vector_store="chroma")

    retriever = factory._make_dense_retriever(s, verses, fake_embedder)

    assert isinstance(retriever, DenseRetriever)


def test_make_dense_retriever_invalid_value_raises(verses, fake_embedder):
    s = _settings(vector_store="bogus")
    with pytest.raises(ValueError, match="bogus"):
        factory._make_dense_retriever(s, verses, fake_embedder)


class DummyKiwiTokenizer:
    pass


class DummyMecabTokenizer:
    pass


def test_make_tokenizer_kiwi_returns_kiwi_tokenizer(monkeypatch):
    monkeypatch.setattr(factory, "KiwiTokenizer", DummyKiwiTokenizer)
    s = _settings(tokenizer="kiwi")

    tokenizer = factory._make_tokenizer(s)

    assert isinstance(tokenizer, DummyKiwiTokenizer)


def test_make_tokenizer_mecab_returns_mecab_tokenizer(monkeypatch):
    monkeypatch.setattr(factory, "MecabTokenizer", DummyMecabTokenizer)
    s = _settings(tokenizer="mecab")

    tokenizer = factory._make_tokenizer(s)

    assert isinstance(tokenizer, DummyMecabTokenizer)


def test_make_tokenizer_invalid_value_raises():
    s = _settings(tokenizer="bogus")
    with pytest.raises(ValueError, match="bogus"):
        factory._make_tokenizer(s)


def test_make_bm25_retriever_without_cache_tokenizes_directly(verses):
    from bible_search.tokenizer import KiwiTokenizer
    from bible_search.retrievers.bm25 import BM25Retriever

    s = _settings(use_token_cache=False)
    retriever = factory._make_bm25_retriever(s, verses, KiwiTokenizer())

    assert isinstance(retriever, BM25Retriever)


def test_make_bm25_retriever_with_missing_cache_raises(tmp_path, verses):
    from bible_search.tokenizer import KiwiTokenizer

    missing_path = tmp_path / "does_not_exist.json"
    s = _settings(use_token_cache=True, token_cache_path=str(missing_path))

    with pytest.raises(FileNotFoundError, match="build_token_cache"):
        factory._make_bm25_retriever(s, verses, KiwiTokenizer())


def test_make_bm25_retriever_with_cache_uses_pretokenized_corpus(tmp_path, verses, monkeypatch):
    from bible_search.tokenizer import KiwiTokenizer

    cache_path = tmp_path / "token_cache.json"
    cache_path.write_text("{}")  # 존재하기만 하면 됨; load_token_cache는 monkeypatch로 대체
    s = _settings(use_token_cache=True, token_cache_path=str(cache_path))

    fake_corpus = [["dummy"] for _ in verses]
    captured = {}

    def fake_load_token_cache(path, vs, tokenizer=None):
        captured["path"] = path
        captured["verses"] = vs
        captured["tokenizer"] = tokenizer
        return fake_corpus

    monkeypatch.setattr(factory, "load_token_cache", fake_load_token_cache)

    tok = KiwiTokenizer()
    retriever = factory._make_bm25_retriever(s, verses, tok)

    assert captured["verses"] == verses
    assert retriever._bm25 is not None


def test_make_bm25_retriever_with_cache_passes_tokenizer_for_mismatch_check(
        tmp_path, verses, monkeypatch):
    from bible_search.tokenizer import KiwiTokenizer

    cache_path = tmp_path / "token_cache.json"
    cache_path.write_text("{}")
    s = _settings(use_token_cache=True, token_cache_path=str(cache_path))

    captured = {}

    def fake_load_token_cache(path, vs, tokenizer=None):
        captured["tokenizer"] = tokenizer
        return [["dummy"] for _ in vs]

    monkeypatch.setattr(factory, "load_token_cache", fake_load_token_cache)

    tok = KiwiTokenizer()
    factory._make_bm25_retriever(s, verses, tok)

    # 캐시를 만든 토크나이저와 다르면 조용히 망가지지 않도록, 현재 쓰는
    # 토크나이저를 load_token_cache에 넘겨 이름 검증을 하게 한다.
    assert captured["tokenizer"] is tok
