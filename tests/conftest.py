from pathlib import Path
import numpy as np
import pytest
from bible_search.data.loader import load_verses

FIXTURE = Path(__file__).parent / "data" / "verses_fixture.jsonl"

@pytest.fixture
def verses():
    return load_verses(FIXTURE)


class FakeEmbedder:
    """토큰 집합을 고정 차원 멀티-핫 벡터로 인코딩하는 결정적 가짜 임베더."""
    VOCAB = ["여호와", "목자", "소망", "구원", "빛", "창조", "태초", "희망"]

    def encode(self, texts):
        vecs = []
        for t in texts:
            v = np.array([1.0 if w in t else 0.0 for w in self.VOCAB], dtype=np.float32)
            n = np.linalg.norm(v)
            vecs.append(v / n if n > 0 else v)
        return np.vstack(vecs)


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()
