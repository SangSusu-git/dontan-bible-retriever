"""고어체 검증 + Dense 임계값 튜닝 하니스.

라벨링된 현대어 패러프레이즈 질의 세트(tests/data/eval_set.jsonl)로 실제
인덱스(chroma/verses)와 실제 데이터(data/verses.jsonl)를 대상으로 검색
서비스를 돌려, dense_threshold 후보값들에 대해 recall@all / top-3
hit-rate를 표로 출력한다. 서비스(BM25 토큰화 + KURE 임베더 로딩)는 비용이
크므로 한 번만 만들고, 각 임계값마다 DenseRetriever의 _threshold만 바꿔
재사용한다.

또한 스펙 3.5 요구대로 Kiwi 토큰화 샘플 몇 개를 출력해 어간 붕괴 여부를
육안으로 확인할 수 있게 한다.
"""
import json
from pathlib import Path

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer
from bible_search.factory import build_search_service

EVAL = Path("tests/data/eval_set.jsonl")
THRESHOLDS = (0.55, 0.60, 0.65, 0.70, 0.80, 0.90)


def load_eval() -> list[dict]:
    rows = []
    for line in EVAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def evaluate(service, rows: list[dict]) -> tuple[float, float]:
    """recall@all 과 top-3 hit-rate 계산.

    recall@all: 기대 id 중 exact+related 어디에든 등장한 비율 (전체 expected
    id 개수 기준).
    top-3 hit-rate: 질의별로 exact_matches + related_matches를 순서대로
    이어붙인 목록의 앞 3개 안에 기대 id가 하나라도 있으면 그 질의는 hit.
    """
    hits = total_expected = 0
    top3_hits = 0
    for row in rows:
        expected = set(row["expected_ids"])
        resp = service.search(row["query"])
        combined = resp.exact_matches + resp.related_matches
        got = {r.verse.id for r in combined}
        hits += len(expected & got)
        total_expected += len(expected)

        top3_ids = {r.verse.id for r in combined[:3]}
        if expected & top3_ids:
            top3_hits += 1

    recall = hits / total_expected if total_expected else 0.0
    top3_hit_rate = top3_hits / len(rows) if rows else 0.0
    return recall, top3_hit_rate


def main() -> None:
    rows = load_eval()

    print("=== Kiwi 토큰화 샘플 (어간 붕괴 확인) ===")
    tok = KiwiTokenizer()
    settings = get_settings()
    for verse in load_verses(settings.data_path)[:5]:
        print(verse.text, "->", tok.tokenize(verse.text))

    print(f"\n=== 임계값 스윕 (eval_set.jsonl {len(rows)}개 질의) ===")
    print("서비스 빌드 중 (BM25 토큰화 + KURE 임베더 로딩, 1회만 수행)...")
    service = build_search_service(settings)

    results = []
    for th in THRESHOLDS:
        service._dense._threshold = th
        recall, top3_hit_rate = evaluate(service, rows)
        results.append((th, recall, top3_hit_rate))

    print(f"\n{'threshold':>10} | {'recall@all':>10} | {'top3_hit_rate':>13}")
    print("-" * 40)
    for th, recall, top3_hit_rate in results:
        print(f"{th:>10.2f} | {recall:>10.3f} | {top3_hit_rate:>13.3f}")


if __name__ == "__main__":
    main()
