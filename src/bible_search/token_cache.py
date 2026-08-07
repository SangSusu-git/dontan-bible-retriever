"""Kiwi 형태소 분석 결과를 파일로 캐싱해 콜드스타트 시간을 줄인다.

BM25 인덱스 빌드 시간의 대부분(~11s/12s)은 31,017개 구절을 Kiwi로 토큰화하는
데 소요된다. 토큰화 결과를 디스크에 저장해두면 재기동 시 토큰화를 건너뛰고
BM25Okapi 생성(~0.1s)만 수행할 수 있다.
"""
import hashlib
import json
from pathlib import Path

from bible_search.models import Verse
from bible_search.tokenizer import KiwiTokenizer


def _fingerprint(verse_ids: list[str]) -> str:
    """구절 id 집합에 대한 순서 무관 지문. 캐시가 최신인지 검증하는 데 쓴다."""
    joined = "|".join(sorted(verse_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_token_cache(verses: list[Verse], tokenizer: KiwiTokenizer,
                      out_path: str | Path) -> int:
    """모든 구절을 토큰화해 out_path에 JSON으로 저장한다. 토큰화한 구절 수를 반환."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entries = [
        {"id": v.id, "tokens": tokenizer.tokenize(v.text)}
        for v in verses
    ]
    data = {
        "count": len(verses),
        "fingerprint": _fingerprint([v.id for v in verses]),
        "verses": entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return len(verses)


def load_token_cache(out_path: str | Path, verses: list[Verse]) -> list[list[str]]:
    """캐시를 로드해 verses와 같은 순서의 토큰 리스트를 반환한다.

    캐시가 verses와 맞지 않으면(구절 수 불일치 또는 id 지문 불일치) 오래된
    캐시를 조용히 잘못 사용하지 않도록 명확한 에러를 낸다. id 집합은 같지만
    순서만 다르면 verses 순서에 맞춰 재정렬해 반환한다.
    """
    out_path = Path(out_path)
    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)

    cached_count = data.get("count")
    if cached_count != len(verses):
        raise ValueError(
            f"토큰 캐시가 최신 상태가 아닙니다: 캐시된 구절 수({cached_count})가 "
            f"현재 구절 수({len(verses)})와 다릅니다. "
            f"scripts/build_token_cache.py를 다시 실행하세요. (경로: {out_path})"
        )

    expected_fp = _fingerprint([v.id for v in verses])
    cached_fp = data.get("fingerprint")
    if cached_fp != expected_fp:
        raise ValueError(
            "토큰 캐시가 최신 상태가 아닙니다: 구절 id 지문이 일치하지 않습니다. "
            f"scripts/build_token_cache.py를 다시 실행하세요. (경로: {out_path})"
        )

    id_to_tokens = {entry["id"]: entry["tokens"] for entry in data["verses"]}
    try:
        return [id_to_tokens[v.id] for v in verses]
    except KeyError as e:
        raise ValueError(
            f"토큰 캐시에 구절 id {e}가 없습니다. "
            f"scripts/build_token_cache.py를 다시 실행하세요. (경로: {out_path})"
        ) from e
