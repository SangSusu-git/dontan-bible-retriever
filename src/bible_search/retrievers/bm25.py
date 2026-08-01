from rank_bm25 import BM25Okapi
from bible_search.models import Verse, SearchResult
from bible_search.tokenizer import KiwiTokenizer


class BM25Retriever:
    def __init__(self, verses: list[Verse], tokenizer: KiwiTokenizer) -> None:
        self._verses = verses
        self._tokenizer = tokenizer
        corpus = [tokenizer.tokenize(v.text) for v in verses]
        # rank_bm25는 빈 문서를 허용하지만, 전부 빈 코퍼스는 방어
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        if self._bm25 is None:
            return []
        q_tokens = self._tokenizer.tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        ranked = [
            SearchResult(verse=self._verses[i], score=float(s), source="bm25")
            for i, s in enumerate(scores)
            if s > 0
        ]
        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked if limit is None else ranked[:limit]
