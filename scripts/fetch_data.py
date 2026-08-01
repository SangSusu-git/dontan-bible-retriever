"""성경 텍스트 확보 스크립트 (Plan 2 Task 5).

공개 GitHub 리포지토리 thiagobodruk/bible (MIT License)에서 한국어 성경 전체
텍스트(json/ko_ko.json)를 내려받아 정본 JSONL(data/verses.jsonl)로 변환한다.

Step 1(공개 텍스트 파일 탐색) 결과:
  - 소스: https://github.com/thiagobodruk/bible (MIT License — 코드/데이터 파일
    전체에 적용됨, README에서도 자유 이용을 명시)
  - 원본 파일: https://raw.githubusercontent.com/thiagobodruk/bible/master/json/ko_ko.json
  - 번역본: 원문에 '가라사대' 등 고어체 표현이 있어 개역한글(1961/1997)로 판단됨
    (개역개정이 아님 — 정확성을 위해 translation 필드를 "개역한글"로 표기).
  - 라이선스가 재배포에 적합하고, 어차피 data/*.jsonl은 .gitignore로 로컬 전용이라
    이 소스로 충분하다고 판단, Step 2(사용자 API)는 불필요.

데이터 품질 주의사항 (원본 README: "these files may contain minor issues
related to encoding and syntax" 를 실제로 확인함):
  - 전체 구절의 약 5%(1,837개의 "!" 중 1,831개)에 공백 뒤에 붙는 " !" 토큰이
    원문에 없는 크롤러 아티팩트로 섞여 있다. holybible.or.kr(RHV) 원문과
    대조한 결과 창세기 1:1 등에는 느낌표가 없음을 확인했다. 다만 원문에는
    "할렐루야!", "두려워 말라!", "보라!" 처럼 단어에 공백 없이 바로 붙는 **진짜**
    느낌표도 6곳 존재한다(개역한글이 감탄문에 "!"를 실제로 사용함). 따라서
    앞에 공백이 있는 "!"만 제거하고, 단어에 바로 붙은 "!"는 보존한다
    (공백 1개 이상 + "!" 패턴만 매치하는 정규식 사용 — 전역
    `text.replace("!", "")`를 쓰면 이 진짜 느낌표까지 지워버리므로 사용하지
    않는다. 정확한 패턴은 아래 clean_text() 참고).
  - 인용구를 backtick(`)으로 열고 HTML 엔티티 &#x27;(')로 닫는 패턴이 있다.
    둘 다 작은따옴표(')로 정규화한다.

이 스크립트는 실행할 때마다 원본을 새로 내려받는다(로컬 캐시 없음). 네트워크가
막혀 있으면 명확한 에러 메시지와 함께 종료한다.
"""
from __future__ import annotations

import html
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover - certifi is a transitive dep of chromadb/httpx
    _SSL_CONTEXT = None

SOURCE_URL = (
    "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/ko_ko.json"
)
TRANSLATION = "개역한글"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "verses.jsonl"

# 66권 표준 순서. thiagobodruk/bible ko_ko.json의 최상위 배열 순서 및 각 책의
# chapters 길이(창세기 50장, 시편 150편, 이사야 66장, 마태복음 28장 등)를
# 실제로 대조하여 확인한 매핑이다.
BOOK_ORDER: list[tuple[str, str]] = [
    ("gn", "창세기"),
    ("ex", "출애굽기"),
    ("lv", "레위기"),
    ("nm", "민수기"),
    ("dt", "신명기"),
    ("js", "여호수아"),
    ("jud", "사사기"),
    ("rt", "룻기"),
    ("1sm", "사무엘상"),
    ("2sm", "사무엘하"),
    ("1kgs", "열왕기상"),
    ("2kgs", "열왕기하"),
    ("1ch", "역대상"),
    ("2ch", "역대하"),
    ("ezr", "에스라"),
    ("ne", "느헤미야"),
    ("et", "에스더"),
    ("job", "욥기"),
    ("ps", "시편"),
    ("prv", "잠언"),
    ("ec", "전도서"),
    ("so", "아가"),
    ("is", "이사야"),
    ("jr", "예레미야"),
    ("lm", "예레미야애가"),
    ("ez", "에스겔"),
    ("dn", "다니엘"),
    ("ho", "호세아"),
    ("jl", "요엘"),
    ("am", "아모스"),
    ("ob", "오바댜"),
    ("jn", "요나"),
    ("mi", "미가"),
    ("na", "나훔"),
    ("hk", "하박국"),
    ("zp", "스바냐"),
    ("hg", "학개"),
    ("zc", "스가랴"),
    ("ml", "말라기"),
    ("mt", "마태복음"),
    ("mk", "마가복음"),
    ("lk", "누가복음"),
    ("jo", "요한복음"),
    ("act", "사도행전"),
    ("rm", "로마서"),
    ("1co", "고린도전서"),
    ("2co", "고린도후서"),
    ("gl", "갈라디아서"),
    ("eph", "에베소서"),
    ("ph", "빌립보서"),
    ("cl", "골로새서"),
    ("1ts", "데살로니가전서"),
    ("2ts", "데살로니가후서"),
    ("1tm", "디모데전서"),
    ("2tm", "디모데후서"),
    ("tt", "디도서"),
    ("phm", "빌레몬서"),
    ("hb", "히브리서"),
    ("jm", "야고보서"),
    ("1pe", "베드로전서"),
    ("2pe", "베드로후서"),
    ("1jo", "요한일서"),
    ("2jo", "요한이서"),
    ("3jo", "요한삼서"),
    ("jd", "유다서"),
    ("re", "요한계시록"),
]


def fetch_raw(url: str = SOURCE_URL, timeout: int = 30) -> list[dict]:
    """원본 JSON을 내려받아 파싱한다. 실패 시 명확한 에러로 중단한다."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "dontan-bible-retriever/fetch_data (+local beta)"}
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_SSL_CONTEXT
        ) as resp:
            raw_bytes = resp.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(
            f"원본 다운로드 실패({url}): {e}. 네트워크 연결을 확인하거나, "
            "이 소스가 더 이상 유효하지 않다면 큐레이션 폴백 데이터셋을 준비해야 한다."
        ) from e

    text = raw_bytes.decode("utf-8-sig")
    data = json.loads(text)
    if not isinstance(data, list) or len(data) < 60:
        raise ValueError(
            f"예상치 못한 응답 형식(HTML 에러 페이지일 가능성): type={type(data)}, "
            f"len={len(data) if hasattr(data, '__len__') else '?'}"
        )
    return data


def clean_text(text: str) -> str:
    """크롤러 아티팩트를 제거하고 공백을 정규화한다."""
    text = html.unescape(text)  # &#x27; -> '
    text = text.replace("`", "'")  # 인용 여는 부호 정규화
    # 크롤러 아티팩트인 " !"(공백+느낌표)만 제거. 단어에 바로 붙은 진짜 느낌표
    # (예: "할렐루야!", "두려워 말라!")는 원문 표현이므로 보존한다.
    text = re.sub(r"\s+!", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_verses(raw: list[dict]) -> list[dict]:
    by_abbrev = {b["abbrev"]: b["chapters"] for b in raw}
    missing = [ab for ab, _kr in BOOK_ORDER if ab not in by_abbrev]
    if missing:
        raise ValueError(f"소스에 예상된 책이 없음: {missing}")

    verses: list[dict] = []
    seen_ids: set[str] = set()
    for abbrev, book_kr in BOOK_ORDER:
        chapters = by_abbrev[abbrev]
        for ch_idx, verse_list in enumerate(chapters, start=1):
            for v_idx, raw_text in enumerate(verse_list, start=1):
                text = clean_text(raw_text)
                if not text:
                    continue
                vid = f"{TRANSLATION}:{book_kr}:{ch_idx}:{v_idx}"
                if vid in seen_ids:
                    raise ValueError(f"중복 id 발생: {vid}")
                seen_ids.add(vid)
                verses.append(
                    {
                        "id": vid,
                        "book": book_kr,
                        "chapter": ch_idx,
                        "verse": v_idx,
                        "text": text,
                        "translation": TRANSLATION,
                    }
                )
    return verses


def write_jsonl(verses: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for v in verses:
            f.write(json.dumps(v, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    print(f"소스에서 다운로드 중: {SOURCE_URL}", file=sys.stderr)
    raw = fetch_raw()
    print(f"{len(raw)}권 로드 완료. 정본 스키마로 변환 중...", file=sys.stderr)
    verses = build_verses(raw)
    write_jsonl(verses)
    print(f"{len(verses)}개 구절을 {OUTPUT_PATH}에 기록했습니다.", file=sys.stderr)


if __name__ == "__main__":
    main()
