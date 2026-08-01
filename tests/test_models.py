from bible_search.models import Verse, SearchResult

def test_verse_fields():
    v = Verse(id="개역개정:창세기:1:1", book="창세기", chapter=1, verse=1,
              text="태초에 하나님이 천지를 창조하시니라", translation="개역개정")
    assert v.book == "창세기"
    assert v.chapter == 1

def test_search_result_wraps_verse():
    v = Verse(id="x", book="창세기", chapter=1, verse=1, text="t", translation="개역개정")
    r = SearchResult(verse=v, score=0.5, source="bm25")
    assert r.verse is v
    assert r.source == "bm25"
