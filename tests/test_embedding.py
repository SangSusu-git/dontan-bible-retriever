import numpy as np
import pytest
from bible_search.embedding import HfApiEmbedder, KureEmbedder

@pytest.mark.slow
def test_kure_embedder_normalized_shape():
    emb = KureEmbedder()
    vecs = emb.encode(["여호와는 나의 목자시니", "빛이 있으라"])
    assert vecs.shape[0] == 2
    # L2 정규화 확인 (norm ~ 1.0)
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


class FakeHfClient:
    """feature_extraction이 미리 지정된 형태를 돌려주는 가짜 HF 클라이언트."""

    def __init__(self, response):
        self._response = response

    def feature_extraction(self, text, model):
        return self._response


def test_hf_api_embedder_raises_without_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("huggingface_hub.get_token", lambda: None)
    with pytest.raises(ValueError):
        HfApiEmbedder()


def test_hf_api_embedder_encode_1d_response(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    emb = HfApiEmbedder()
    dim = 4
    emb._client = FakeHfClient([0.1, 0.2, 0.3, 0.4])  # (dim,) 형태

    vecs = emb.encode(["여호와는 나의 목자시니"])

    assert vecs.shape == (1, dim)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)


def test_hf_api_embedder_encode_2d_response(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    emb = HfApiEmbedder()
    dim = 4
    emb._client = FakeHfClient([[0.1, 0.2, 0.3, 0.4]])  # (1, dim) 형태

    vecs = emb.encode(["빛이 있으라"])

    assert vecs.shape == (1, dim)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)


def test_hf_api_embedder_encode_multiple_texts(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    emb = HfApiEmbedder()

    responses = iter([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]])

    class MultiResponseClient:
        def feature_extraction(self, text, model):
            return next(responses)

    emb._client = MultiResponseClient()

    vecs = emb.encode(["첫번째 문장", "두번째 문장"])

    assert vecs.shape == (2, 4)
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)


def test_hf_api_embedder_unexpected_rank_raises(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "fake-token")
    emb = HfApiEmbedder()
    # 토큰 단위 (seq, dim) 응답 — 평균 풀링하지 않고 에러를 내야 함
    emb._client = FakeHfClient([[0.1, 0.2, 0.3] for _ in range(5)])

    with pytest.raises(ValueError, match=r"\(5, 3\)"):
        emb.encode(["단일 문장"])
