"""오프라인 토큰 캐시 빌드: Kiwi 형태소 분석 결과를 파일로 캐싱해 콜드스타트 단축."""
import time
from pathlib import Path

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.factory import _make_tokenizer
from bible_search.token_cache import build_token_cache


def main() -> None:
    s = get_settings()
    start = time.perf_counter()

    verses = load_verses(s.data_path)
    print(f"loaded {len(verses)} verses from {s.data_path}")

    tokenizer = _make_tokenizer(s)
    print(f"using tokenizer: {type(tokenizer).__name__} (BIBLE_TOKENIZER={s.tokenizer})")
    count = build_token_cache(verses, tokenizer, s.token_cache_path)
    elapsed = time.perf_counter() - start

    out_path = Path(s.token_cache_path)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"tokenized {count} verses -> {out_path} ({size_mb:.2f} MB) in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
