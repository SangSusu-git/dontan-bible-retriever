import re
from bible_search.models import Verse, SearchResult

_STRIP = re.compile(r"[\s\W]+", re.UNICODE)


def _normalize(s: str) -> str:
    return _STRIP.sub("", s)


class ExactMatcher:
    def __init__(self, verses: list[Verse]) -> None:
        self._norm = [(_normalize(v.text), v) for v in verses]

    def search(self, query: str) -> list[SearchResult]:
        q = _normalize(query)
        if not q:
            return []
        return [
            SearchResult(verse=v, score=1.0, source="exact")
            for norm_text, v in self._norm
            if q in norm_text
        ]
