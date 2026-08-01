from bible_search.models import Verse, SearchResult
from bible_search.embedding import Embedder


# Chroma는 단일 add 호출당 배치 크기 상한(버전에 따라 ~5461)이 있어, 그보다
# 작은 값으로 나눠 적재한다. 전체 성경(약 3만 절)은 한 번에 넣을 수 없다.
_ADD_BATCH_SIZE = 5000


def add_verses_to_collection(collection, verses: list[Verse], embedder: Embedder,
                             batch_size: int = _ADD_BATCH_SIZE) -> None:
    if not verses:
        return
    embeddings = embedder.encode([v.text for v in verses])
    ids = [v.id for v in verses]
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            embeddings=[e.tolist() for e in embeddings[start:end]],
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
