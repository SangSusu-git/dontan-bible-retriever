from dataclasses import dataclass
from bible_search.models import SearchResult
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.fusion import reciprocal_rank_fusion


@dataclass(frozen=True)
class SearchResponse:
    exact_matches: list[SearchResult]
    related_matches: list[SearchResult]


class SearchService:
    def __init__(self, exact: ExactMatcher, bm25: BM25Retriever, dense: DenseRetriever,
                 rrf_k: int = 60, max_results: int = 500) -> None:
        self._exact = exact
        self._bm25 = bm25
        self._dense = dense
        self._rrf_k = rrf_k
        self._max_results = max_results

    def search(self, query: str) -> SearchResponse:
        exact = self._exact.search(query)
        exact_ids = {r.verse.id for r in exact}

        bm25 = self._bm25.search(query)
        dense = self._dense.search(query)
        fused = reciprocal_rank_fusion([bm25, dense], k=self._rrf_k)

        related = [r for r in fused if r.verse.id not in exact_ids][: self._max_results]
        return SearchResponse(exact_matches=exact, related_matches=related)
