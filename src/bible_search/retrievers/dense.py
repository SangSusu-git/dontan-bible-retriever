from bible_search.models import Verse, SearchResult
from bible_search.embedding import Embedder


def add_verses_to_collection(collection, verses: list[Verse], embedder: Embedder) -> None:
    if not verses:
        return
    embeddings = embedder.encode([v.text for v in verses])
    collection.add(
        ids=[v.id for v in verses],
        embeddings=[e.tolist() for e in embeddings],
    )


class DenseRetriever:
    def __init__(self, collection, verses: list[Verse], embedder: Embedder,
                 threshold: float = 0.8) -> None:
        self._collection = collection
        self._embedder = embedder
        self._threshold = threshold
        self._by_id = {v.id: v for v in verses}

    def search(self, query: str) -> list[SearchResult]:
        q = self._embedder.encode([query])[0]
        n = self._collection.count()
        if n == 0:
            return []
        res = self._collection.query(
            query_embeddings=[q.tolist()],
            n_results=n,
        )
        ids = res["ids"][0]
        distances = res["distances"][0]
        out: list[SearchResult] = []
        for vid, dist in zip(ids, distances):
            sim = 1.0 - float(dist)
            if sim >= self._threshold and vid in self._by_id:
                out.append(SearchResult(verse=self._by_id[vid], score=sim, source="dense"))
        out.sort(key=lambda r: r.score, reverse=True)
        return out
