from bible_search.retrievers.exact import ExactMatcher

def test_exact_finds_contained_phrase(verses):
    m = ExactMatcher(verses)
    results = m.search("천지를 창조")
    ids = [r.verse.id for r in results]
    assert "개역개정:창세기:1:1" in ids
    assert all(r.source == "exact" for r in results)

def test_exact_ignores_whitespace_and_punctuation(verses):
    m = ExactMatcher(verses)
    # 공백/문장부호가 달라도 매칭되어야 한다
    assert m.search("천지 를  창조")
    assert m.search("천지를,창조")

def test_exact_no_match_returns_empty(verses):
    m = ExactMatcher(verses)
    assert m.search("존재하지않는구절ZZZ") == []
