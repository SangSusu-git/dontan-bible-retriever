from bible_search.tokenizer import KiwiTokenizer

def test_tokenize_extracts_content_stems():
    tok = KiwiTokenizer()
    tokens = tok.tokenize("태초에 하나님이 천지를 창조하시니라")
    # 조사(에,이,를)·어미(하시니라의 하/시/니라)는 빠지고 내용어 어간이 남는다
    assert "태초" in tokens
    assert "창조" in tokens
    assert "천지" in tokens
    # 조사는 포함되지 않아야 한다
    assert "를" not in tokens
    assert "에" not in tokens

def test_tokenize_query_matches_verse_stem():
    tok = KiwiTokenizer()
    q = set(tok.tokenize("태초 창조"))
    v = set(tok.tokenize("태초에 하나님이 천지를 창조하시니라"))
    # 질의 토큰이 모두 구절 토큰에 포함되어야 BM25 매칭이 성립
    assert q.issubset(v)
