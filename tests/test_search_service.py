import itertools
import chromadb
from bible_search.tokenizer import KiwiTokenizer
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection
from bible_search.search_service import SearchService, SearchResponse

_counter = itertools.count()


def _service(verses, embedder, threshold=0.5, **kwargs):
    client = chromadb.EphemeralClient()
    # chromadb.EphemeralClient() instances share in-process storage, so each
    # call needs a distinct collection name to avoid "already exists" errors
    # across the test functions in this module (same issue test_dense.py
    # avoids by using "dense-test" / "dense-test-2").
    col = client.create_collection(f"svc-test-{next(_counter)}", metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, embedder)
    return SearchService(
        exact=ExactMatcher(verses),
        bm25=BM25Retriever(verses, KiwiTokenizer()),
        dense=DenseRetriever(col, verses, embedder, threshold=threshold),
        **kwargs,
    )


def test_search_returns_response_shape(verses, fake_embedder):
    svc = _service(verses, fake_embedder)
    resp = svc.search("여호와")
    assert isinstance(resp, SearchResponse)
    assert isinstance(resp.exact_matches, list)
    assert isinstance(resp.related_matches, list)


def test_exact_hit_appears_in_exact_section(verses, fake_embedder):
    svc = _service(verses, fake_embedder)
    resp = svc.search("천지를 창조")
    exact_ids = [r.verse.id for r in resp.exact_matches]
    assert "개역개정:창세기:1:1" in exact_ids


def test_related_excludes_exact_ids(verses, fake_embedder):
    svc = _service(verses, fake_embedder)
    resp = svc.search("여호와는 나의 목자")
    exact_ids = {r.verse.id for r in resp.exact_matches}
    related_ids = {r.verse.id for r in resp.related_matches}
    assert exact_ids
    assert exact_ids.isdisjoint(related_ids)


def test_max_results_caps_related(verses, fake_embedder):
    svc = _service(verses, fake_embedder)
    svc._max_results = 1
    resp = svc.search("여호와")
    assert len(resp.related_matches) <= 1


def test_search_applies_bm25_top_k(verses, fake_embedder):
    client = chromadb.EphemeralClient()
    col = client.create_collection(f"svc-test-{next(_counter)}", metadata={"hnsw:space": "cosine"})
    add_verses_to_collection(col, verses, fake_embedder)

    real_bm25 = BM25Retriever(verses, KiwiTokenizer())
    seen = {}

    class SpyBM25:
        def search(self, query, limit=None):
            seen["limit"] = limit
            return real_bm25.search(query, limit=limit)

    svc = SearchService(
        exact=ExactMatcher(verses),
        bm25=SpyBM25(),
        dense=DenseRetriever(col, verses, fake_embedder, threshold=0.5),
        bm25_top_k=1,
    )
    svc.search("여호와")
    assert seen["limit"] == 1  # SearchService must forward bm25_top_k as the BM25 limit


def test_fusion_weighted_produces_results(verses, fake_embedder):
    svc = _service(verses, fake_embedder, fusion="weighted")
    resp = svc.search("여호와 목자")
    assert resp.related_matches
    assert all(r.source == "hybrid" for r in resp.related_matches)


def test_fusion_weighted_ranks_full_coverage_above_partial(verses, fake_embedder):
    # "여호와 목자"에 완전히(둘 다) 매칭되는 시편 23:1이, "여호와"만 매칭되는
    # 이사야 40:31보다 위에 와야 한다 — 실험이 검증한 핵심 동작.
    svc = _service(
        verses, fake_embedder, fusion="weighted",
        w_bm25=0.7, w_dense=1.0, w_cov=2.0, w_prox=0.5,
    )
    resp = svc.search("여호와 목자")
    ids = [r.verse.id for r in resp.related_matches]
    assert "개역개정:시편:23:1" in ids
    assert "개역개정:이사야:40:31" in ids
    assert ids.index("개역개정:시편:23:1") < ids.index("개역개정:이사야:40:31")


def test_fusion_rrf_still_behaves_as_before(verses, fake_embedder):
    svc = _service(verses, fake_embedder, fusion="rrf")
    resp = svc.search("여호와는 나의 목자")
    exact_ids = {r.verse.id for r in resp.exact_matches}
    related_ids = {r.verse.id for r in resp.related_matches}
    assert exact_ids
    assert exact_ids.isdisjoint(related_ids)
    assert all(r.source == "rrf" for r in resp.related_matches)


def test_invalid_fusion_raises_valueerror(verses, fake_embedder):
    svc = _service(verses, fake_embedder, fusion="bogus")
    try:
        svc.search("여호와")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid fusion setting")
