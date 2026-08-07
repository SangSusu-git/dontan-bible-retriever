"""Kiwi 모델 타입별 메모리 사용량과 토큰화 결과 동일성을 비교한다.

배포 시 메모리를 줄이려면 더 가벼운 모델을 쓸 수 있는지 확인하는 용도.
토큰화 결과가 달라지면 BM25 인덱스/토큰 캐시를 다시 만들어야 하므로 반드시 함께 검증한다.

사용법:
    PYTHONPATH=src python scripts/probe_kiwi_memory.py
"""

import json
import subprocess
import sys

# 각 설정을 별도 프로세스에서 측정해야 정확하다(한 프로세스에 여러 모델을 올리면 섞임).
CHILD = r'''
import json, resource, sys
def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024*1024) if sys.platform == "darwin" else r / 1024

kwargs = json.loads(sys.argv[1])
before = rss_mb()
from kiwipiepy import Kiwi
try:
    kiwi = Kiwi(**kwargs)
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {e}"})); raise SystemExit
after_init = rss_mb()

CONTENT_TAGS = frozenset({
    "NNG","NNP","NNB","NR","NP","VV","VA","VX","VCP","VCN",
    "MAG","MAJ","SL","SH","SN","XR",
})
samples = [
    "태초에 하나님이 천지를 창조하시니라",
    "사랑은 오래 참고, 사랑은 온유하며, 투기하는 자가 되지 아니하며",
    "여호와는 나의 목자시니 내가 부족함이 없으리로다",
    "오직 여호와를 앙망하는 자는 새 힘을 얻으리니",
    "수고하고 무거운 짐진 자들아 다 내게로 오라",
    "너의 처음 사랑을 버렸느니라",
]
toks = [[t.form.lower() for t in kiwi.tokenize(s) if t.tag in CONTENT_TAGS] for s in samples]
print(json.dumps({"init_mb": after_init - before, "peak_mb": rss_mb(), "tokens": toks}))
'''

CONFIGS = [
    ("기본값 (현재 사용 중)", {}),
    ("multi/typo 사전 끄기", {"load_multi_dict": False, "load_typo_dict": False}),
    ("+ default 사전도 끄기", {"load_multi_dict": False, "load_typo_dict": False,
                            "load_default_dict": False}),
    ("integrate_allomorph=False", {"load_multi_dict": False, "load_typo_dict": False,
                                   "integrate_allomorph": False}),
]


def main() -> None:
    baseline_tokens = None
    print(f"{'설정':<26} {'Kiwi 메모리':>12} {'피크':>9}  {'토큰 동일':>9}")
    print("-" * 62)
    for label, kwargs in CONFIGS:
        proc = subprocess.run(
            [sys.executable, "-c", CHILD, json.dumps(kwargs)],
            capture_output=True, text=True,
        )
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            print(f"{label:<26} {'실행 실패':>12}   {proc.stderr.strip()[:40]}")
            continue
        if "error" in data:
            print(f"{label:<26} {'미지원':>12}   {data['error'][:40]}")
            continue
        if baseline_tokens is None:
            baseline_tokens = data["tokens"]
            same = "기준"
        else:
            same = "동일" if data["tokens"] == baseline_tokens else "다름"
        print(f"{label:<26} {data['init_mb']:>9.1f} MB {data['peak_mb']:>8.1f} {same:>10}")

    print("-" * 62)
    print("* 토큰이 '다름'이면 token_cache와 BM25 인덱스를 다시 만들어야 한다.")


if __name__ == "__main__":
    main()
