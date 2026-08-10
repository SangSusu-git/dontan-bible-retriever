"""대한성서공회(bskorea.or.kr) 공식 개역한글 본문을 수집해 정본 JSONL을 만든다.

배경: 기존 소스(thiagobodruk/bible ko_ko.json)는 전수조사 결과 1,189장 중
79장에서 절 수가 표준과 어긋났다(연쇄 밀림, 절 유실, 병합). 문장부호도
원문과 다른 오염(인용부호·나열 쉼표 등)이 광범위했다. 개역한글판은
저작권이 만료(2011)된 공유 저작물이므로, 공식 온라인 본문을 직접
수집하는 것이 "실제 판매되는 개역한글"에 가장 충실하다.

파싱 규칙:
  - 각 절은 <span class="number">N ...</span> 뒤의 텍스트.
  - <font class="smallTitle">(편집 소제목·시편 표제)는 절 번호가 없는
    요소이므로 본문에서 제외한다 — 공식 인쇄본의 절 본문과 동일해진다.
  - 절 번호는 1..N 연속이어야 하며, 아니면 즉시 실패한다(조용한 오염 방지).

사용법:
    python scripts/fetch_data_bskorea.py            # 전체 66권 수집 (~7분)
    python scripts/fetch_data_bskorea.py --limit 2  # 앞 2권만 (테스트)
"""

import argparse
import html as html_mod
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

# macOS 시스템 파이썬은 CA 번들이 비어 SSL 검증이 실패한다 — certifi로 보완.
try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # certifi가 없으면 기본 컨텍스트 시도
    _SSL_CTX = ssl.create_default_context()

BASE = "https://www.bskorea.or.kr/bible/korbibReadpage.php?version=HAN&book={code}&chap={chap}"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "verses.jsonl"
TRANSLATION = "개역한글"
DELAY_SEC = 0.35

# (한글 책명, 후보 URL 코드들, 장 수) — 장 수는 전 역본 공통 표준.
BOOKS: list[tuple[str, list[str], int]] = [
    ("창세기", ["gen"], 50), ("출애굽기", ["exo"], 40), ("레위기", ["lev"], 27),
    ("민수기", ["num"], 36), ("신명기", ["deu"], 34), ("여호수아", ["jos"], 24),
    ("사사기", ["jdg"], 21), ("룻기", ["rut"], 4), ("사무엘상", ["1sa"], 31),
    ("사무엘하", ["2sa"], 24), ("열왕기상", ["1ki"], 22), ("열왕기하", ["2ki"], 25),
    ("역대상", ["1ch"], 29), ("역대하", ["2ch"], 36), ("에스라", ["ezr"], 10),
    ("느헤미야", ["neh"], 13), ("에스더", ["est"], 10), ("욥기", ["job"], 42),
    ("시편", ["psa"], 150), ("잠언", ["pro"], 31), ("전도서", ["ecc"], 12),
    ("아가", ["sng", "sol", "sos"], 8), ("이사야", ["isa"], 66),
    ("예레미야", ["jer"], 52), ("예레미야애가", ["lam"], 5),
    ("에스겔", ["ezk", "eze"], 48), ("다니엘", ["dan"], 12),
    ("호세아", ["hos"], 14), ("요엘", ["jol", "joe"], 3), ("아모스", ["amo"], 9),
    ("오바댜", ["oba"], 1), ("요나", ["jnh", "jon"], 4), ("미가", ["mic"], 7),
    ("나훔", ["nam", "nah", "nhm"], 3), ("하박국", ["hab"], 3), ("스바냐", ["zep", "zph"], 3),
    ("학개", ["hag"], 2), ("스가랴", ["zec", "zch"], 14), ("말라기", ["mal"], 4),
    ("마태복음", ["mat"], 28), ("마가복음", ["mrk", "mar"], 16),
    ("누가복음", ["luk"], 24), ("요한복음", ["jhn", "joh"], 21),
    ("사도행전", ["act"], 28), ("로마서", ["rom"], 16),
    ("고린도전서", ["1co"], 16), ("고린도후서", ["2co"], 13),
    ("갈라디아서", ["gal"], 6), ("에베소서", ["eph"], 6),
    ("빌립보서", ["php", "phi"], 4), ("골로새서", ["col"], 4),
    ("데살로니가전서", ["1th"], 5), ("데살로니가후서", ["2th"], 3),
    ("디모데전서", ["1ti"], 6), ("디모데후서", ["2ti"], 4),
    ("디도서", ["tit"], 3), ("빌레몬서", ["phm"], 1), ("히브리서", ["heb"], 13),
    ("야고보서", ["jas", "jam"], 5), ("베드로전서", ["1pe"], 5), ("베드로후서", ["2pe"], 3),
    ("요한일서", ["1jn", "1jo"], 5), ("요한이서", ["2jn", "2jo"], 1),
    ("요한삼서", ["3jn", "3jo"], 1), ("유다서", ["jud", "jde"], 1),
    ("요한계시록", ["rev"], 22),
]

# 절 마커는 "1" 외에 범위 합절 "1-3"(시편 92편 등)도 존재한다.
VERSE_SPLIT_RE = re.compile(r'<span class="number">(\d+(?:-\d+)?)&nbsp;')
TAG_RE = re.compile(r"<[^>]+>")
SMALL_TITLE_RE = re.compile(r'<font class="smallTitle">.*?</font>(?:<br\s*/?>)*', re.DOTALL)


CACHE_DIR = Path.home() / ".cache" / "bskorea_han"


def fetch(url: str, retries: int = 3) -> str:
    # 파서 수정 후 재실행 시 서버를 다시 두드리지 않도록 페이지를 캐시한다.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "_", url.split("?", 1)[-1])
    cache_file = CACHE_DIR / f"{key}.html"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bible-app data build; personal use)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as r:
                page = r.read().decode("utf-8", errors="replace")
            cache_file.write_text(page, encoding="utf-8")
            time.sleep(DELAY_SEC)
            return page
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def parse_chapter(page: str, book: str, chap: int) -> list[dict]:
    # 본문 영역만 대충 한정: 첫 번째 절 마커부터 잘라도 충분하지만,
    # smallTitle이 절 사이에 끼는 경우가 있어 전체에서 제거 후 분할한다.
    page = SMALL_TITLE_RE.sub("", page)
    parts = VERSE_SPLIT_RE.split(page)
    # parts = [머리말, '1', 본문1, '2', 본문2, ...]
    if len(parts) < 3:
        raise ValueError(f"{book} {chap}장: 절 마커를 찾지 못함")
    verses = []
    range_end: dict[int, int] = {}
    for i in range(1, len(parts) - 1, 2):
        marker = parts[i]
        # 범위 합절 "1-3": 본문은 시작 절 번호에 붙이고, 나머지는 아래
        # 합절 채움 로직이 "(1절과 같음)"으로 메운다.
        head, _, tail = marker.partition("-")
        num = int(head)
        if tail:
            range_end[num] = int(tail)
        raw = parts[i + 1]
        # 절 본문은 다음 구조 블록(<div>, <script> 등) 전까지다. 마지막 절이
        # 뒤따르는 네비게이션/팝업("성경 단어 검색" 등)을 삼키지 않게 자른다.
        for stop in ("<script", "<div", "<form", "<input", "<table"):
            raw = raw.split(stop, 1)[0]
        # 인라인 태그(<font class="name">노아</font>가 등)는 단어 중간에 끼므로
        # 공백이 아니라 빈 문자열로 제거해야 "노아 가"처럼 쪼개지지 않는다.
        text = TAG_RE.sub("", raw)
        text = html_mod.unescape(text)
        text = text.replace("\xa0", " ")
        # 난외주(각주) 참조 마커 "1)" "2)" 는 본문이 아니다 — 제거.
        text = re.sub(r"\d+\)", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        verses.append({"num": num, "text": text})
    nums = [v["num"] for v in verses]
    if not nums or nums[0] != 1 or any(b <= a for a, b in zip(nums, nums[1:])):
        raise ValueError(f"{book} {chap}장: 절 번호 이상 {nums[:5]}...{nums[-3:]}")
    empty = [v["num"] for v in verses if not v["text"]]
    if empty:
        raise ValueError(f"{book} {chap}장: 빈 본문 절 {empty}")
    # 합절 처리: 공식본이 두 절을 합쳐 인쇄한 경우(예: 신명기 6:18-19) 뒤 번호의
    # 마커가 페이지에 없다. 주소 공백이 생기지 않도록 "(N절과 같음)"으로 채운다.
    filled: list[dict] = []
    prev = 0
    for v in verses:
        for missing in range(prev + 1, v["num"]):
            filled.append({"num": missing, "text": f"({prev}절과 같음)"})
        filled.append(v)
        prev = v["num"]
    # 장 끝이 범위 합절("17-18")로 끝나면 위 루프가 못 채우므로 여기서 채운다.
    last = verses[-1]["num"]
    for missing in range(last + 1, range_end.get(last, last) + 1):
        filled.append({"num": missing, "text": f"({last}절과 같음)"})
    if len(filled) != len(verses):
        gaps = [f["num"] for f in filled if f["text"].endswith("절과 같음)")]
        print(f"    합절 채움: {book} {chap}장 {gaps}", flush=True)
    return filled


def resolve_code(name: str, candidates: list[str]) -> str:
    for code in candidates:
        page = fetch(BASE.format(code=code, chap=1))
        if 'class="number"' in page and name[:2] in page:
            return code
    raise RuntimeError(f"{name}: URL 코드를 찾지 못함 (후보 {candidates})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="앞 N권만 수집(테스트)")
    args = ap.parse_args()

    books = BOOKS[: args.limit] if args.limit else BOOKS
    all_rows: list[dict] = []
    t0 = time.time()
    total_ch = sum(b[2] for b in books)
    done_ch = 0

    for name, candidates, chapters in books:
        code = resolve_code(name, candidates)
        for chap in range(1, chapters + 1):
            page = fetch(BASE.format(code=code, chap=chap))
            verses = parse_chapter(page, name, chap)
            for v in verses:
                all_rows.append({
                    "id": f"{TRANSLATION}:{name}:{chap}:{v['num']}",
                    "book": name, "chapter": chap, "verse": v["num"],
                    "text": v["text"], "translation": TRANSLATION,
                })
            done_ch += 1
            if done_ch % 100 == 0:
                el = time.time() - t0
                print(f"  {done_ch}/{total_ch}장 ({el:.0f}s, {len(all_rows):,}절)", flush=True)
        print(f"{name} 완료 ({chapters}장, code={code})", flush=True)

    ids = [r["id"] for r in all_rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("중복 id 발생")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n총 {len(all_rows):,}절 → {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
