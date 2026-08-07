import pytest
from bible_search.models import Verse
from bible_search.tokenizer import KiwiTokenizer
from bible_search.token_cache import build_token_cache, load_token_cache


def test_round_trip_matches_direct_tokenization(tmp_path, verses):
    tokenizer = KiwiTokenizer()
    out_path = tmp_path / "token_cache.json"

    count = build_token_cache(verses, tokenizer, out_path)
    assert count == len(verses)

    loaded = load_token_cache(out_path, verses)
    expected = [tokenizer.tokenize(v.text) for v in verses]
    assert loaded == expected


def test_load_creates_parent_dirs(tmp_path, verses):
    tokenizer = KiwiTokenizer()
    out_path = tmp_path / "nested" / "dir" / "token_cache.json"

    build_token_cache(verses, tokenizer, out_path)

    assert out_path.exists()


def test_stale_cache_detects_removed_verse_raises(tmp_path, verses):
    tokenizer = KiwiTokenizer()
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, tokenizer, out_path)

    fewer_verses = verses[:-1]
    with pytest.raises(ValueError):
        load_token_cache(out_path, fewer_verses)


def test_stale_cache_detects_changed_id_raises(tmp_path, verses):
    tokenizer = KiwiTokenizer()
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, tokenizer, out_path)

    changed = list(verses)
    changed[0] = Verse(
        id="changed-id",
        book=changed[0].book,
        chapter=changed[0].chapter,
        verse=changed[0].verse,
        text=changed[0].text,
        translation=changed[0].translation,
    )
    with pytest.raises(ValueError):
        load_token_cache(out_path, changed)


def test_reordered_verses_returns_reordered_tokens(tmp_path, verses):
    tokenizer = KiwiTokenizer()
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, tokenizer, out_path)

    reordered = list(reversed(verses))
    loaded = load_token_cache(out_path, reordered)

    # 원래 verses의 첫 구절은 reordered에서 마지막 인덱스에 있다.
    expected_first_tokens = tokenizer.tokenize(verses[0].text)
    assert loaded[-1] == expected_first_tokens
    assert len(loaded) == len(reordered)
