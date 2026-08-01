from pathlib import Path
from bible_search.data.loader import load_verses

FIXTURE = Path(__file__).parent / "data" / "verses_fixture.jsonl"

def test_load_verses_count():
    verses = load_verses(FIXTURE)
    assert len(verses) == 8

def test_load_verses_parses_fields():
    verses = load_verses(FIXTURE)
    first = verses[0]
    assert first.book == "창세기"
    assert first.chapter == 1
    assert first.verse == 1
    assert "천지를 창조하시니라" in first.text

def test_load_verses_ignores_blank_lines(tmp_path):
    p = tmp_path / "v.jsonl"
    p.write_text(
        '{"id":"a","book":"창세기","chapter":1,"verse":1,"text":"t","translation":"개역개정"}\n\n',
        encoding="utf-8",
    )
    assert len(load_verses(p)) == 1
