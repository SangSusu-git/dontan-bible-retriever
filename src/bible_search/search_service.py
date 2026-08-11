from dataclasses import dataclass
from bible_search.models import SearchResult
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.fusion import reciprocal_rank_fusion
from bible_search.ranking import weighted_fusion


@dataclass(frozen=True)
class SearchResponse:
    exact_matches: list[SearchResult]
    related_matches: list[SearchResult]


class SearchService:
    def __init__(self, exact: ExactMatcher, bm25: BM25Retriever, dense: DenseRetriever,
                 rrf_k: int = 60, max_results: int = 50, bm25_top_k: int = 30,
                 fusion: str = "weighted", w_bm25: float = 0.7, w_dense: float = 1.0,
                 w_cov: float = 2.0, w_prox: float = 0.5) -> None:
        self._exact = exact
        self._bm25 = bm25
        self._dense = dense
        self._rrf_k = rrf_k
        self._max_results = max_results
        self._bm25_top_k = bm25_top_k
        self._fusion = fusion
        self._w_bm25 = w_bm25
        self._w_dense = w_dense
        self._w_cov = w_cov
        self._w_prox = w_prox

    def search(self, query: str) -> SearchResponse:
        exact = self._exact.search(query)
        exact_ids = {r.verse.id for r in exact}

        bm25 = self._bm25.search(query, limit=self._bm25_top_k)
        dense = self._dense.search(query)

        if self._fusion == "rrf":
            fused = reciprocal_rank_fusion([bm25, dense], k=self._rrf_k)
        elif self._fusion == "weighted":
            fused = weighted_fusion(
                bm25, dense, query,
                w_bm25=self._w_bm25, w_dense=self._w_dense,
                w_cov=self._w_cov, w_prox=self._w_prox,
            )
        else:
            raise ValueError(
                f"알 수 없는 fusion 설정: {self._fusion!r} "
                "(유효한 값: 'weighted', 'rrf')"
            )

        related = [r for r in fused if r.verse.id not in exact_ids][: self._max_results]
        return SearchResponse(exact_matches=exact, related_matches=related)
