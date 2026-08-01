import numpy as np
import pytest
from bible_search.embedding import KureEmbedder

@pytest.mark.slow
def test_kure_embedder_normalized_shape():
    emb = KureEmbedder()
    vecs = emb.encode(["여호와는 나의 목자시니", "빛이 있으라"])
    assert vecs.shape[0] == 2
    # L2 정규화 확인 (norm ~ 1.0)
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
