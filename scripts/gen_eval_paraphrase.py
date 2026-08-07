"""덜 유명한 구절 대상 패러프레이즈 평가 세트를 생성한다.

각 항목은 (현대어 질의, 대상 책, 본문 검증용 부분 문자열)로 정의한다.
장절 번호를 사람이 기억에 의존해 적으면 틀리기 쉬우므로, 해당 책에서
검증 문자열을 포함하는 구절을 찾아 정확한 id를 자동 확정한다.
검증 문자열이 여러 구절에 걸리면 모두 정답으로 인정한다(expected_ids).

출력: tests/data/eval_paraphrase.jsonl
사용법: PYTHONPATH=src python scripts/gen_eval_paraphrase.py
"""

import json
from pathlib import Path

from bible_search.data.loader import load_verses

OUT = Path("tests/data/eval_paraphrase.jsonl")

# (질의, 책, 검증 문자열) — 잘 알려지지 않은 사건/구절 위주로 구성
CANDIDATES = [
    ("하늘까지 닿은 사다리로 천사들이 오르내리는 꿈", "창세기", "사닥다리"),
    ("광야에서 내린 만나의 맛은 꿀 과자 같았다", "출애굽기", "꿀 섞은 과자"),
    ("나귀가 입을 열어 주인에게 말하다", "민수기", "나귀 입을 여시니"),
    ("물을 개처럼 핥아 먹은 사람들만 택하다", "사사기", "핥는 자"),
    ("우상 다곤이 궤 앞에 얼굴을 땅에 대고 쓰러지다", "사무엘상", "다곤이 여호와의 궤 앞에서 엎드러져"),
    ("까마귀들이 아침저녁으로 떡과 고기를 가져다 주다", "열왕기상", "까마귀들이"),
    ("물에 빠진 도끼가 떠오르는 기적", "열왕기하", "도끼"),
    ("재 가운데 앉아 기와 조각으로 몸을 긁는 고통", "욥기", "기와 조각"),
    ("목마른 사슴이 시냇물을 찾듯 주를 찾다", "시편", "사슴이 시냇물"),
    ("네 양식을 물 위에 던지면 여러 날 후에 도로 찾는다", "전도서", "식물을 물 위에 던지라"),
    ("해 그림자가 십 도 뒤로 물러간 표적", "이사야", "십도를 물러가게"),
    ("마른 뼈들이 서로 연결되어 큰 군대로 살아나다", "에스겔", "저 뼈가 들어 맞아서"),
    ("잔치 중 벽에 손가락이 나타나 글자를 쓰다", "다니엘", "손가락이 나와서"),
    ("요나의 머리 위에 그늘을 만들어 준 박 넝쿨", "요나", "박 넝쿨"),
    ("물고기 입에서 나온 돈으로 성전세를 내다", "마태복음", "입을 열면 돈 한 세겔"),
    ("귀신 들린 돼지 떼가 비탈로 내리달아 바다에 빠져 죽다", "마가복음", "돼지에게로 들어가니"),
    ("키 작은 세리가 뽕나무에 올라가 예수를 보려 하다", "누가복음", "뽕나무에 올라가니"),
    ("설교 시간에 졸다가 삼층 창에서 떨어진 청년", "사도행전", "삼층 누에서 떨어지"),
    ("손을 문 독사를 불에 떨어버리고 해를 입지 않다", "사도행전", "짐승을 불에 떨어"),
    ("혀는 작은 지체지만 온 몸을 더럽히는 불이다", "야고보서", "혀는 곧 불이요"),
    ("차지도 뜨겁지도 않은 미지근한 믿음을 토하리라", "요한계시록", "미지근하여"),
    ("해를 입은 여자가 아이를 낳으려 하고 용이 삼키려 하다", "요한계시록", "해를 입은 한 여자"),
    ("영원한 것을 위해 잠깐의 환난은 가볍다", "고린도후서", "잠시 받는 환난의 경"),
    ("녹지 않는 보물을 하늘에 쌓아 두라", "마태복음", "보물을 하늘에 쌓아"),
]


def main() -> None:
    verses = load_verses("data/verses.jsonl")
    by_book: dict[str, list] = {}
    for v in verses:
        by_book.setdefault(v.book, []).append(v)

    rows, failed = [], []
    for query, book, marker in CANDIDATES:
        matches = [v for v in by_book.get(book, []) if marker in v.text]
        if not matches:
            failed.append((query, book, marker))
            continue
        rows.append({
            "query": query,
            "expected_ids": [v.id for v in matches],
            "book": book,
            "tier": "paraphrase",
        })

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"확정: {len(rows)}개 / 후보 {len(CANDIDATES)}개 → {OUT}")
    for r in rows[:5]:
        tgt = r["expected_ids"][0].split(":", 1)[1]
        extra = f" 외 {len(r['expected_ids'])-1}" if len(r["expected_ids"]) > 1 else ""
        print(f"  \"{r['query'][:30]}\" -> {tgt}{extra}")
    if failed:
        print("\n검증 실패(본문 불일치 — 수정 필요):")
        for q, b, m in failed:
            print(f"  [{b}] '{m}' 없음  (질의: {q[:24]})")


if __name__ == "__main__":
    main()
