"""HF Inference API의 rate limit과 응답 특성을 실측한다 (읽기 전용).

측정 항목:
  1) 연속 호출 20회 — 성공률, 지연 분포, rate limit 발생 여부
  2) 동시 호출 5/10회 — 동시성 한계
  3) 오류 발생 시 응답 코드와 메시지(429 = rate limit, 402 = 크레딧 소진)

크레딧 소모는 https://huggingface.co/settings/billing 에서 실행 전후로 확인한다.

사용법:
    export HF_TOKEN=hf_xxx
    python scripts/measure_hf_limits.py
"""

import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

MODEL = "nlpai-lab/KURE-v1"
QUERY = "여호와는 나의 목자시니"


def make_client():
    from huggingface_hub import InferenceClient

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN 필요")
    return InferenceClient(token=token)


def one_call(client, text: str):
    """(성공여부, 지연, 오류메시지) 반환."""
    t0 = time.time()
    try:
        out = client.feature_extraction(text, model=MODEL)
        np.asarray(out, dtype=np.float32)
        return True, time.time() - t0, None
    except Exception as e:  # 상태 코드가 메시지에 포함됨
        return False, time.time() - t0, f"{type(e).__name__}: {str(e)[:120]}"


def sequential(client, n: int):
    print(f"\n=== 연속 호출 {n}회 ===")
    lat, fails = [], []
    for i in range(n):
        ok, dt, err = one_call(client, f"{QUERY} {i}")
        if ok:
            lat.append(dt)
        else:
            fails.append((i, err))
            print(f"  [{i:>2}] 실패: {err}")
    print(f"  성공 {len(lat)}/{n}")
    if lat:
        print(f"  지연 최소 {min(lat):.2f}s / 중앙 {statistics.median(lat):.2f}s / 최대 {max(lat):.2f}s")
    return len(lat), fails


def concurrent(client, n: int):
    print(f"\n=== 동시 호출 {n}회 ===")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(lambda i: one_call(client, f"{QUERY} 동시 {i}"), range(n)))
    total = time.time() - t0
    ok = sum(1 for r in results if r[0])
    print(f"  성공 {ok}/{n}, 전체 소요 {total:.2f}s")
    for i, (s, _, err) in enumerate(results):
        if not s:
            print(f"  [{i}] 실패: {err}")
    return ok


def main() -> None:
    client = make_client()
    print("측정 시작 — 실행 전 https://huggingface.co/settings/billing 의 사용액을 확인해두세요.")

    n_ok, fails = sequential(client, 20)
    ok5 = concurrent(client, 5)
    ok10 = concurrent(client, 10)

    total_calls = 20 + 5 + 10
    print("\n" + "=" * 56)
    print(f"총 호출 {total_calls}회 (성공 {n_ok + ok5 + ok10}회)")
    if any("429" in (e or "") for _, e in fails):
        print("⚠️ 429(rate limit) 발생 — 무료 티어 호출 빈도 제한 있음")
    elif fails:
        print("⚠️ 일부 실패 — 위 메시지 확인")
    else:
        print("✅ 실패 없음 — 이 정도 빈도에서는 rate limit 미발생")
    print("\n이제 billing 페이지에서 사용액 증가분을 확인하세요.")
    print(f"  (증가분 ÷ {total_calls} = 검색 1회당 비용, $0.10 ÷ 그 값 = 월 가능 검색 수)")


if __name__ == "__main__":
    main()
