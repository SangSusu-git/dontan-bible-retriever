from bible_search.models import Verse, SearchResult


def reciprocal_rank_fusion(result_lists: list[list[SearchResult]],
                           k: int = 60) -> list[SearchResult]:
    scores: dict[str, float] = {}
    verses: dict[str, Verse] = {}
    for results in result_lists:
        for rank, r in enumerate(results):
            vid = r.verse.id
            scores[vid] = scores.get(vid, 0.0) + 1.0 / (k + rank + 1)
            verses.setdefault(vid, r.verse)
    fused = [
        SearchResult(verse=verses[vid], score=score, source="rrf")
        for vid, score in scores.items()
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused
