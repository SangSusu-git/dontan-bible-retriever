"""경량 구성의 메모리를 구성 요소별로 측정한다 (배포 사양 산정용).

사용법:
    PYTHONPATH=src BIBLE_API_KEY=x python scripts/profile_memory.py
"""

import os
import resource
import sys


def rss_mb() -> float:
    """현재 프로세스 RSS(MB). macOS는 바이트, 리눅스는 KB 단위로 반환한다."""
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == "darwin" else r / 1024


def step(label: str, prev: float) -> float:
    cur = rss_mb()
    print(f"  {label:<42} +{cur - prev:7.1f} MB   (누적 {cur:7.1f} MB)")
    return cur


def main() -> None:
    os.environ.setdefault("BIBLE_API_KEY", "profile")
    base = rss_mb()
    print(f"시작 (파이썬 인터프리터)                        {base:7.1f} MB\n")

    import numpy as np  # noqa: F401
    prev = step("numpy import", base)

    from bible_search.config import get_settings
    from bible_search.data.loader import load_verses
    prev = step("bible_search import", prev)

    s = get_settings()
    verses = load_verses(s.data_path)
    prev = step(f"구절 로드 ({len(verses):,}개)", prev)

    from bible_search.retrievers.exact import ExactMatcher
    exact = ExactMatcher(verses)  # noqa: F841
    prev = step("ExactMatcher (정규화 텍스트 사본)", prev)

    from bible_search.token_cache import load_token_cache
    corpus = load_token_cache(s.token_cache_path, verses)
    prev = step("토큰 캐시 로드 (파이썬 문자열 리스트)", prev)

    from bible_search.tokenizer import KiwiTokenizer
    tok = KiwiTokenizer()
    prev = step("Kiwi 초기화", prev)

    from bible_search.retrievers.bm25 import BM25Retriever
    bm25 = BM25Retriever(verses, tok, corpus=corpus)  # noqa: F841
    prev = step("BM25 인덱스 (rank_bm25 doc_freqs)", prev)

    del corpus
    prev = step("토큰 리스트 해제 후", prev)

    from bible_search.vectorstore import load_numpy_index
    vectors, ids, _basis = load_numpy_index(s.numpy_index_path)
    prev = step(f"numpy 벡터 로드 {vectors.shape} {vectors.dtype}", prev)

    print(f"\n  최종 RSS: {rss_mb():.1f} MB")
    print(f"  벡터 이론값: {vectors.nbytes / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
