import chromadb
import pytest
from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection


@pytest.fixture
def dense(verses, fake_embedder):
    client = chromadb.EphemeralClient()
    col = client.create_collection("dense-test", metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, fake_embedder)
    return DenseRetriever(col, verses, fake_embedder, threshold=0.5)


def test_dense_returns_semantically_similar(dense):
    results = dense.search("여호와")
    ids = [r.verse.id for r in results]
    assert "개역개정:시편:23:1" in ids
    assert all(r.source == "dense" for r in results)
    assert all(r.score >= 0.5 for r in results)


def test_dense_threshold_excludes_unrelated(verses, fake_embedder):
    client = chromadb.EphemeralClient()
    col = client.create_collection("dense-test-2", metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, fake_embedder)
    r = DenseRetriever(col, verses, fake_embedder, threshold=0.99)
    assert r.search("컴퓨터") == []


def test_add_verses_batches_when_over_batch_size(verses, fake_embedder):
    # batch_size가 구절 수보다 작아도 전부 적재되어야 한다 (Chroma add 배치 상한 대응).
    # 실제 성경은 3만 절이라 단일 add 상한(~5461)을 넘으므로 분할 적재가 필수.
    client = chromadb.EphemeralClient()
    col = client.create_collection("dense-batch", metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, fake_embedder, batch_size=2)
    assert col.count() == len(verses)
