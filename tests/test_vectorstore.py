import itertools

import chromadb
import numpy as np

from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection
from bible_search.vectorstore import NumpyDenseRetriever, build_numpy_index, load_numpy_index

_counter = itertools.count()


def test_build_and_load_round_trip(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    count = build_numpy_index(verses, fake_embedder, str(out_dir))

    assert count == len(verses)
    assert (out_dir / "vectors.npy").exists()
    assert (out_dir / "ids.json").exists()

    vectors, ids = load_numpy_index(str(out_dir))

    assert ids == [v.id for v in verses]
    assert vectors.dtype == np.float32
    assert vectors.shape == (len(verses), len(fake_embedder.VOCAB))


def test_build_numpy_index_is_idempotent(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    second_count = build_numpy_index(verses, fake_embedder, str(out_dir))

    assert second_count == len(verses)
    vectors, ids = load_numpy_index(str(out_dir))
    assert ids == [v.id for v in verses]
    assert vectors.shape == (len(verses), len(fake_embedder.VOCAB))


def test_float16_storage_round_trips_to_float32(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir), dtype="float16")

    raw = np.load(out_dir / "vectors.npy")
    assert raw.dtype == np.float16

    vectors, _ = load_numpy_index(str(out_dir))
    assert vectors.dtype == np.float32
    assert np.allclose(vectors, raw.astype(np.float32))


def test_search_returns_dense_source_sorted_and_above_threshold(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    vectors, ids = load_numpy_index(str(out_dir))

    retriever = NumpyDenseRetriever(vectors, ids, verses, fake_embedder, threshold=0.5)
    results = retriever.search("여호와")

    result_ids = [r.verse.id for r in results]
    assert "개역개정:시편:23:1" in result_ids
    assert all(r.source == "dense" for r in results)
    assert all(r.score >= 0.5 for r in results)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_high_threshold_excludes_unrelated(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    vectors, ids = load_numpy_index(str(out_dir))

    retriever = NumpyDenseRetriever(vectors, ids, verses, fake_embedder, threshold=0.99)
    assert retriever.search("컴퓨터") == []


def test_search_empty_index_returns_empty(verses, fake_embedder):
    vectors = np.zeros((0, len(fake_embedder.VOCAB)), dtype=np.float32)
    retriever = NumpyDenseRetriever(vectors, [], verses, fake_embedder, threshold=0.5)
    assert retriever.search("여호와") == []


def test_numpy_and_chroma_are_equivalent(tmp_path, verses, fake_embedder):
    # Chroma와 numpy 두 백엔드가 같은 verses + embedder에 대해 동일한 결과를
    # 내는지 확인한다. 이 테스트가 통과해야 벡터 저장소 교체가 안전하다고
    # 볼 수 있다.
    client = chromadb.EphemeralClient()
    name = f"equiv-test-{next(_counter)}"
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, fake_embedder)
    chroma_retriever = DenseRetriever(col, verses, fake_embedder, threshold=0.5)

    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    vectors, ids = load_numpy_index(str(out_dir))
    numpy_retriever = NumpyDenseRetriever(vectors, ids, verses, fake_embedder, threshold=0.5)

    for query in ("여호와", "소망", "빛", "컴퓨터"):
        chroma_results = chroma_retriever.search(query)
        numpy_results = numpy_retriever.search(query)

        chroma_ids = [r.verse.id for r in chroma_results]
        numpy_ids = [r.verse.id for r in numpy_results]
        assert chroma_ids == numpy_ids

        chroma_scores = {r.verse.id: r.score for r in chroma_results}
        numpy_scores = {r.verse.id: r.score for r in numpy_results}
        for vid in chroma_ids:
            assert abs(chroma_scores[vid] - numpy_scores[vid]) < 1e-3
