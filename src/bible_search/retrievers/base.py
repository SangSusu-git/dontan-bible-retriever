from typing import Protocol
from bible_search.models import SearchResult


class Retriever(Protocol):
    def search(self, query: str) -> list[SearchResult]:
        ...
