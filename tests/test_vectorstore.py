import itertools

import chromadb
import numpy as np
import pytest

from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection
from bible_search.vectorstore import NumpyDenseRetriever, build_numpy_index, load_numpy_index

_counter = itertools.count()


def test_build_and_load_round_trip(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    count = build_numpy_index(verses, fake_embedder, str(out_dir))

    assert count == len(verses)
    assert (out_dir / "vectors.npy").exists()
    assert (out_dir / "ids.json").exists()

    vectors, ids, basis = load_numpy_index(str(out_dir))

    assert ids == [v.id for v in verses]
    assert vectors.dtype == np.float32
    assert vectors.shape == (len(verses), len(fake_embedder.VOCAB))
    assert basis is None
    assert not (out_dir / "basis.npy").exists()


def test_build_numpy_index_is_idempotent(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    second_count = build_numpy_index(verses, fake_embedder, str(out_dir))

    assert second_count == len(verses)
    vectors, ids, basis = load_numpy_index(str(out_dir))
    assert ids == [v.id for v in verses]
    assert vectors.shape == (len(verses), len(fake_embedder.VOCAB))


def test_float16_storage_round_trips_to_float32(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir), dtype="float16")

    raw = np.load(out_dir / "vectors.npy")
    assert raw.dtype == np.float16

    vectors, _, _ = load_numpy_index(str(out_dir))
    assert vectors.dtype == np.float32
    assert np.allclose(vectors, raw.astype(np.float32))


def test_search_returns_dense_source_sorted_and_above_threshold(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))
    vectors, ids, basis = load_numpy_index(str(out_dir))

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
    vectors, ids, basis = load_numpy_index(str(out_dir))

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
    vectors, ids, basis = load_numpy_index(str(out_dir))
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


def test_build_numpy_index_with_dim_writes_basis(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    orig_dim = len(fake_embedder.VOCAB)
    k = 6
    build_numpy_index(verses, fake_embedder, str(out_dir), dim=k)

    assert (out_dir / "basis.npy").exists()

    vectors, ids, basis = load_numpy_index(str(out_dir))
    assert ids == [v.id for v in verses]
    assert basis is not None
    assert basis.dtype == np.float32
    assert basis.shape == (k, orig_dim)
    assert vectors.shape == (len(verses), k)


def test_load_numpy_index_without_dim_returns_none_basis(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    build_numpy_index(verses, fake_embedder, str(out_dir))

    assert not (out_dir / "basis.npy").exists()

    vectors, ids, basis = load_numpy_index(str(out_dir))
    assert basis is None


def test_build_numpy_index_dim_too_large_raises(tmp_path, verses, fake_embedder):
    out_dir = tmp_path / "numpy_index"
    orig_dim = len(fake_embedder.VOCAB)

    with pytest.raises(ValueError, match=str(orig_dim)):
        build_numpy_index(verses, fake_embedder, str(out_dir), dim=orig_dim)

    with pytest.raises(ValueError):
        build_numpy_index(verses, fake_embedder, str(out_dir), dim=orig_dim + 1)


def test_numpy_dense_retriever_mismatched_basis_raises(verses, fake_embedder):
    vocab_dim = len(fake_embedder.VOCAB)
    vectors = np.zeros((len(verses), 4), dtype=np.float32)
    # basis 출력 차원(3)이 vectors 차원(4)과 다름 -> 잘못 짝지어진 기저.
    bad_basis = np.zeros((3, vocab_dim), dtype=np.float32)

    with pytest.raises(ValueError):
        NumpyDenseRetriever(vectors, [v.id for v in verses], verses, fake_embedder,
                            basis=bad_basis)


def test_reduced_dim_retriever_matches_full_dim_retriever(tmp_path, verses, fake_embedder):
    # conftest의 FakeEmbedder는 8차원 멀티-핫 벡터라 SVD로 정보 손실 없이
    # 축소되는 dim을 보장할 수는 없다. dim=6으로 실측한 결과, 이 8개 fixture
    # 구절에 대한 VOCAB 8개 질의 전부(여호와/목자/소망/구원/빛/창조/태초/희망)와
    # 관련 없는 질의(컴퓨터)에서 threshold=0.5 기준 반환 id 순서가 완전히
    # 동일했다(스코어 값 자체는 투영으로 인해 달라질 수 있음). 그래서 "결과
    # 집합과 순서"를 비교하는 정직한 동등성 검증을 한다 — 스코어 동일성은
    # 요구하지 않는다.
    full_dir = tmp_path / "full"
    reduced_dir = tmp_path / "reduced"
    build_numpy_index(verses, fake_embedder, str(full_dir))
    build_numpy_index(verses, fake_embedder, str(reduced_dir), dim=6)

    full_vectors, full_ids, full_basis = load_numpy_index(str(full_dir))
    reduced_vectors, reduced_ids, reduced_basis = load_numpy_index(str(reduced_dir))
    assert full_basis is None
    assert reduced_basis is not None

    full_retriever = NumpyDenseRetriever(full_vectors, full_ids, verses, fake_embedder,
                                         threshold=0.5)
    reduced_retriever = NumpyDenseRetriever(reduced_vectors, reduced_ids, verses,
                                            fake_embedder, threshold=0.5,
                                            basis=reduced_basis)

    for query in fake_embedder.VOCAB + ["컴퓨터"]:
        full_ids_out = [r.verse.id for r in full_retriever.search(query)]
        reduced_ids_out = [r.verse.id for r in reduced_retriever.search(query)]
        assert reduced_ids_out == full_ids_out, f"query={query!r}"
