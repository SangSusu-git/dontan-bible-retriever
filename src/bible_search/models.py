from dataclasses import dataclass

@dataclass(frozen=True)
class Verse:
    id: str
    book: str
    chapter: int
    verse: int
    text: str
    translation: str

@dataclass(frozen=True)
class SearchResult:
    verse: Verse
    score: float
    source: str
