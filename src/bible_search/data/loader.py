import json
from pathlib import Path
from bible_search.models import Verse


def load_verses(path: str | Path) -> list[Verse]:
    verses: list[Verse] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            verses.append(
                Verse(
                    id=d["id"],
                    book=d["book"],
                    chapter=int(d["chapter"]),
                    verse=int(d["verse"]),
                    text=d["text"],
                    translation=d["translation"],
                )
            )
    return verses
