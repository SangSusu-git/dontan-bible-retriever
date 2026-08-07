import json

import pytest
from bible_search.models import Verse
from bible_search.tokenizer import KiwiTokenizer
from bible_search.token_cache import build_token_cache, load_token_cache


class StubTokenizerA:
    def tokenize(self, text):
        return text.split()


class StubTokenizerB:
    def tokenize(self, text):
        return text.split()


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


def test_cache_records_tokenizer_name(tmp_path, verses):
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, StubTokenizerA(), out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["tokenizer"] == "StubTokenizerA"


def test_load_with_mismatched_tokenizer_raises(tmp_path, verses):
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, StubTokenizerA(), out_path)

    with pytest.raises(ValueError, match="StubTokenizerA"):
        load_token_cache(out_path, verses, tokenizer=StubTokenizerB())


def test_load_with_tokenizer_none_skips_check(tmp_path, verses):
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, StubTokenizerA(), out_path)

    # tokenizer 인자를 생략하면(None) 이름 검증 없이 정상 로드된다.
    loaded = load_token_cache(out_path, verses)
    assert len(loaded) == len(verses)


def test_load_cache_missing_tokenizer_field_skips_check(tmp_path, verses):
    out_path = tmp_path / "token_cache.json"
    build_token_cache(verses, StubTokenizerA(), out_path)

    # tokenizer 필드가 없는 구버전 캐시를 시뮬레이션
    data = json.loads(out_path.read_text(encoding="utf-8"))
    del data["tokenizer"]
    out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    loaded = load_token_cache(out_path, verses, tokenizer=StubTokenizerB())
    assert len(loaded) == len(verses)
