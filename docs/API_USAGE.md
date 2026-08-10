# 성경 검색 API 사용 가이드

한국어 성경(개역한글 31,102구절 — 대한성서공회 공식 본문 기준)을 대상으로 한 **하이브리드 검색 API**입니다.
정확한 문구 일치, 키워드(단어) 검색, 의미(유사 표현) 검색을 한 번의 호출로 처리합니다.

- **Base URL**: `https://bible-search-api-ygj1.onrender.com`
- **인증**: 모든 검색 요청에 `X-API-Key` 헤더 필요 (키는 관리자에게 별도로 받으세요 — 이 문서에는 포함되어 있지 않습니다)

---

## 1. 상태 확인 (인증 불필요)

```
GET /health
```

```bash
curl https://bible-search-api-ygj1.onrender.com/health
# → {"status":"ok"}
```

## 2. 검색

```
POST /search
Content-Type: application/json
X-API-Key: <발급받은 키>

{"query": "검색어"}
```

### curl 예시

```bash
curl -X POST https://bible-search-api-ygj1.onrender.com/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 여기에_키" \
  -d '{"query": "사랑은 오래 참고"}'
```

### Python 예시

```python
import requests

resp = requests.post(
    "https://bible-search-api-ygj1.onrender.com/search",
    headers={"X-API-Key": "여기에_키"},
    json={"query": "사랑은 오래 참고"},
    timeout=90,  # 절전에서 깨어날 때를 대비해 넉넉히
)
data = resp.json()
for m in data["exact_matches"] + data["related_matches"]:
    print(f'{m["book"]} {m["chapter"]}:{m["verse"]}  {m["text"]}')
```

### JavaScript(fetch) 예시

```js
const res = await fetch("https://bible-search-api-ygj1.onrender.com/search", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": "여기에_키" },
  body: JSON.stringify({ query: "사랑은 오래 참고" }),
});
const data = await res.json();
```

## 3. 응답 형식

```jsonc
{
  "query": "사랑은 오래 참고",
  "exact_matches": [          // 검색어가 문자 그대로 포함된 구절 (최우선)
    {
      "id": "개역한글:고린도전서:13:4",
      "book": "고린도전서",
      "chapter": 13,
      "verse": 4,
      "text": "사랑은 오래 참고, 사랑은 온유하며, ...",
      "translation": "개역한글",
      "score": 1.0,
      "source": "exact"
    }
  ],
  "related_matches": [        // 단어/의미가 관련된 구절 (관련도 순, 최대 50건)
    {
      "id": "개역한글:에베소서:4:2",
      "book": "에베소서",
      "chapter": 4,
      "verse": 2,
      "text": "모든 겸손과 온유로 하고 오래 참음으로 ...",
      "translation": "개역한글",
      "score": 0.016,          // 순위 융합(RRF) 점수 — 상대 비교용
      "source": "rrf"
    }
  ]
}
```

| 필드 | 설명 |
|---|---|
| `exact_matches` | 검색어(공백·문장부호 무시)가 그대로 들어있는 구절. 확실한 일치이므로 최상단에 표시 권장 |
| `related_matches` | 키워드 일치 + 의미 유사도를 융합한 관련 구절, 관련도 내림차순 |
| `score` | 정렬용 상대 점수 (절대적 의미 없음 — 순서만 신뢰) |
| `source` | `exact`(정확 일치) 또는 `rrf`(융합 결과) |

## 4. 검색 팁

| 하고 싶은 것 | 이렇게 |
|---|---|
| 기억나는 문구로 구절 찾기 | 문구를 그대로 입력 → `exact_matches`에 등장 (예: `"사랑은 오래 참고"`) |
| 키워드로 찾기 (조사 붙어도 OK) | `"여호와 목자 부족"`, `"멜기세덱의 반차를"` |
| 내용은 아는데 표현을 모를 때 | 현대어로 서술 → 의미 검색이 처리 (예: `"물고기 입에서 나온 돈으로 세금을 내다"` → 마태복음 17:27) |

## 5. 오류 코드

| 코드 | 의미 | 대처 |
|---|---|---|
| 401 | API 키 없음/불일치 | `X-API-Key` 헤더 확인 |
| 422 | 요청 형식 오류 | body가 `{"query": "..."}` JSON인지 확인 |
| 5xx | 서버/업스트림 일시 오류 | 잠시 후 재시도 |

## 6. 꼭 알아둘 운영 특성 (무료 호스팅)

- **절전**: 15분간 요청이 없으면 서버가 잠듭니다. 그 후 첫 요청은 **30~60초** 걸릴 수 있으니 타임아웃을 90초 이상으로 잡으세요. 두 번째 요청부터는 약 1초입니다.
- **의미 검색 한도**: 의미 검색은 외부 임베딩 API(월 무료 한도)를 사용합니다. 한도가 소진되면 해당 월 말까지 의미 검색이 실패(5xx)할 수 있습니다 — 매월 1일 자동 복구됩니다.
- **키 관리**: API 키는 코드 저장소·공개 문서에 올리지 말고, 받은 사람끼리만 공유하세요.

---
문의: 저장소 `SangSusu-git/dontan-bible-retriever` (브랜치 `feature/hybrid-search`)
