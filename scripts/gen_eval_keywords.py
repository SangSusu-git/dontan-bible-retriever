"""66권 전권에서 '낯선 구절' 키워드 평가 세트를 자동 생성한다.

설계:
- 각 권에서 책의 25% / 75% 지점 구절을 후보로 선정 (유명 구절 편향 방지).
- 구절의 어절(공백 단위) 중 코퍼스 전체에서 문서빈도(df)가 가장 낮은 2개를
  질의로 사용한다. 조사가 붙은 원형 어절을 그대로 쓰므로("멜기세덱의"),
  토크나이저가 어간을 제대로 분리해야만 BM25가 맞출 수 있다.
- 두 어절이 구절 안에서 인접하면 Exact 매칭으로 잡히므로, 가능한 한
  비인접 조합을 고른다(토크나이저 변별력 확보).

출력: tests/data/eval_keywords_66.jsonl
  {"query": "...", "expected_ids": ["개역한글:책:장:절"], "book": "...", "tier": "keyword"}

사용법: PYTHONPATH=src python scripts/gen_eval_keywords.py
"""

import json
import re
from collections import Counter
from pathlib import Path

from bible_search.data.loader import load_verses

OUT = Path("tests/data/eval_keywords_66.jsonl")
PER_BOOK = 2
MIN_EOJEOL_LEN = 2
MIN_VERSE_EOJEOLS = 8

_PUNCT = re.compile(r"[^\w가-힣]+")


def clean_eojeol(w: str) -> str:
    return _PUNCT.sub("", w)


def main() -> None:
    verses = load_verses("data/verses.jsonl")

    # 책 등장 순서 보존
    books: list[str] = []
    by_book: dict[str, list] = {}
    for v in verses:
        if v.book not in by_book:
            books.append(v.book)
            by_book[v.book] = []
        by_book[v.book].append(v)

    print(f"책 수: {len(books)}")

    # 어절 문서빈도(df) — 어절이 등장하는 구절 수
    df: Counter = Counter()
    for v in verses:
        seen = set()
        for w in v.text.split():
            w = clean_eojeol(w)
            if len(w) >= MIN_EOJEOL_LEN:
                seen.add(w)
        df.update(seen)

    rows = []
    for book in books:
        vs = by_book[book]
        # 25% / 75% 지점부터 후보 탐색
        anchors = [int(len(vs) * 0.25), int(len(vs) * 0.75)]
        picked_ids = set()
        for anchor in anchors[:PER_BOOK]:
            row = None
            # anchor 주변에서 조건(길이/희귀어)이 맞는 구절을 찾는다
            for off in range(0, len(vs)):
                for idx in {anchor + off, anchor - off}:
                    if not (0 <= idx < len(vs)) or vs[idx].id in picked_ids:
                        continue
                    v = vs[idx]
                    words = [clean_eojeol(w) for w in v.text.split()]
                    cand = [
                        (df[w], pos, w)
                        for pos, w in enumerate(words)
                        if len(w) >= MIN_EOJEOL_LEN and df[w] >= 1
                    ]
                    if len(words) < MIN_VERSE_EOJEOLS or len(cand) < 2:
                        continue
                    cand.sort()
                    first = cand[0]
                    # 비인접 어절 우선(Exact로 잡히지 않게), 없으면 인접 허용
                    second = next(
                        (c for c in cand[1:] if abs(c[1] - first[1]) > 1), cand[1]
                    )
                    a, b = sorted([first, second], key=lambda c: c[1])
                    row = {
                        "query": f"{a[2]} {b[2]}",
                        "expected_ids": [v.id],
                        "book": book,
                        "tier": "keyword",
                        "df": [first[0], second[0]],
                    }
                    picked_ids.add(v.id)
                    break
                if row:
                    break
            if row:
                rows.append(row)

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"생성: {len(rows)}개 질의 → {OUT}")
    covered = {r["book"] for r in rows}
    print(f"커버한 책: {len(covered)}/{len(books)}")
    missing = [b for b in books if b not in covered]
    if missing:
        print("누락:", missing)
    print("\n샘플:")
    for r in rows[::11][:8]:
        print(f"  [{r['book']}] \"{r['query']}\" -> {r['expected_ids'][0].split(':',1)[1]} (df={r['df']})")


if __name__ == "__main__":
    main()
