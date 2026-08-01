# 성경 검색 데이터·API·배포 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan 1의 `bible_search` 엔진에 실제 성경 데이터, Chroma 영속 인덱스, FastAPI + API 키 인증, 고어체 검증 하니스, Docker 배포를 붙여 외부 서비스가 호출 가능한 검색 API로 완성한다.

**Architecture:** 성경 텍스트를 정본 JSONL로 확보 → 오프라인 인덱서가 Chroma에 임베딩을 적재(영속) → FastAPI 앱이 시작 시 JSONL을 읽어 ExactMatcher·BM25를 메모리에 구성하고 Chroma 컬렉션을 열어 `SearchService`를 조립 → `POST /search`가 API 키를 검증하고 `exact_matches`/`related_matches`를 반환. BM25·Exact는 시작 시 재구성(30k 규모라 빠름)하고 Chroma만 디스크에 영속한다.

**Tech Stack:** Plan 1 엔진 + FastAPI, uvicorn, pydantic-settings, chromadb(PersistentClient), Docker.

## Global Constraints

- **선행 조건:** Plan 1(`2026-08-02-hybrid-search-engine.md`)이 완료되어 `bible_search` 패키지가 설치되어 있어야 한다.
- 정본 데이터 포맷은 Plan 1과 동일한 **JSONL**(`id,book,chapter,verse,text,translation`).
- API 인증: `X-API-Key` 헤더 == 설정된 `api_key` 일치 검증. 불일치 시 401.
- 설정은 **환경변수**로 주입(pydantic-settings). 키·경로·임계값·상한 포함.
- Chroma 컬렉션은 코사인 공간(`hnsw:space=cosine`). Dense 임계값 기본 0.8(설정으로 override).
- 데이터·인덱스·모델 산출물은 커밋하지 않는다(`.gitignore`가 이미 처리).
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` 포함.

## File Structure

```
src/bible_search/config.py             # Settings (pydantic-settings)
src/bible_search/indexer.py            # build_index(): 구절 -> Chroma 영속 적재
src/bible_search/factory.py            # build_search_service(settings) -> SearchService
src/bible_search/api.py                # FastAPI 앱, 인증, /search /health
scripts/fetch_data.py                  # 성경 텍스트 확보 -> data/verses.jsonl
scripts/build_index.py                 # 인덱서 실행 CLI
scripts/evaluate.py                    # 고어체 검증/임계값 튜닝 하니스
tests/data/eval_set.jsonl              # 라벨된 질의->정답 구절 세트(검증용)
tests/test_config.py
tests/test_indexer.py
tests/test_api.py
Dockerfile
.dockerignore
.env.example
```

---

### Task 1: 설정(Settings)

**Files:**
- Create: `src/bible_search/config.py`, `.env.example`
- Test: `tests/test_config.py`
- Modify: `pyproject.toml` (의존성에 `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `httpx` 추가)

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings) 필드: `api_key: str`, `data_path: str = "data/verses.jsonl"`, `chroma_path: str = "chroma"`, `chroma_collection: str = "verses"`, `embedding_model: str = "nlpai-lab/KURE-v1"`, `dense_threshold: float = 0.8`, `rrf_k: int = 60`, `max_results: int = 500`. 환경변수 접두어 `BIBLE_`.
  - `get_settings() -> Settings` (lru_cache).

- [ ] **Step 1: 의존성 추가** — `pyproject.toml`의 `dependencies`에 아래 항목 추가

```toml
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic-settings>=2.2",
```
그리고 `[project.optional-dependencies]`의 `dev`에 `"httpx>=0.27"` 추가. 이어서 재설치:
Run: `. .venv/bin/activate && pip install -e ".[dev]"`
Expected: 설치 성공.

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_config.py`

```python
from bible_search.config import Settings

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "secret123")
    s = Settings()
    assert s.api_key == "secret123"
    assert s.dense_threshold == 0.8
    assert s.chroma_collection == "verses"

def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("BIBLE_API_KEY", "k")
    monkeypatch.setenv("BIBLE_DENSE_THRESHOLD", "0.9")
    s = Settings()
    assert s.dense_threshold == 0.9
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/test_config.py -q`
Expected: FAIL (`ModuleNotFoundError: bible_search.config`).

- [ ] **Step 4: 최소 구현** — `src/bible_search/config.py`

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIBLE_", env_file=".env")

    api_key: str
    data_path: str = "data/verses.jsonl"
    chroma_path: str = "chroma"
    chroma_collection: str = "verses"
    embedding_model: str = "nlpai-lab/KURE-v1"
    dense_threshold: float = 0.8
    rrf_k: int = 60
    max_results: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: `.env.example` 작성**

```dotenv
BIBLE_API_KEY=change-me
BIBLE_DATA_PATH=data/verses.jsonl
BIBLE_CHROMA_PATH=chroma
BIBLE_CHROMA_COLLECTION=verses
BIBLE_DENSE_THRESHOLD=0.8
BIBLE_RRF_K=60
BIBLE_MAX_RESULTS=500
```

- [ ] **Step 6: 통과 확인**

Run: `pytest tests/test_config.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add src/bible_search/config.py .env.example pyproject.toml tests/test_config.py
git commit -m "feat: add Settings and web/deploy dependencies"
```

---

### Task 2: 인덱서 (Chroma 영속 적재)

**Files:**
- Create: `src/bible_search/indexer.py`, `scripts/build_index.py`
- Test: `tests/test_indexer.py`

**Interfaces:**
- Consumes: `Verse`, `Embedder`, `add_verses_to_collection`(Plan 1 Task 8), chromadb.
- Produces:
  - `build_index(verses: list[Verse], embedder: Embedder, chroma_path: str, collection_name: str) -> int` — `PersistentClient(chroma_path)`에 `collection_name`(코사인) 컬렉션을 생성(있으면 삭제 후 재생성)하고 구절을 적재, 적재 건수 반환.
  - `scripts/build_index.py` — settings로 JSONL 로드 → KureEmbedder → `build_index` 실행하는 CLI.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_indexer.py`

```python
import numpy as np
import chromadb
from bible_search.indexer import build_index


class FakeEmbedder:
    VOCAB = ["여호와", "목자", "소망", "구원", "빛", "창조", "태초", "희망"]
    def encode(self, texts):
        vecs = []
        for t in texts:
            v = np.array([1.0 if w in t else 0.0 for w in self.VOCAB], dtype=np.float32)
            n = np.linalg.norm(v)
            vecs.append(v / n if n > 0 else v)
        return np.vstack(vecs)


def test_build_index_persists_all_verses(verses, tmp_path):
    path = str(tmp_path / "chroma")
    count = build_index(verses, FakeEmbedder(), path, "verses")
    assert count == len(verses)
    # 다시 열었을 때 영속되어 있어야 한다
    client = chromadb.PersistentClient(path)
    col = client.get_collection("verses")
    assert col.count() == len(verses)


def test_build_index_is_idempotent(verses, tmp_path):
    path = str(tmp_path / "chroma")
    build_index(verses, FakeEmbedder(), path, "verses")
    count = build_index(verses, FakeEmbedder(), path, "verses")  # 재실행
    client = chromadb.PersistentClient(path)
    col = client.get_collection("verses")
    assert col.count() == len(verses)  # 중복 적재되지 않음
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_indexer.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/indexer.py`

```python
import chromadb
from bible_search.models import Verse
from bible_search.embedding import Embedder
from bible_search.retrievers.dense import add_verses_to_collection


def build_index(verses: list[Verse], embedder: Embedder,
                chroma_path: str, collection_name: str) -> int:
    client = chromadb.PersistentClient(chroma_path)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )
    add_verses_to_collection(collection, verses, embedder)
    return collection.count()
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_indexer.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: CLI 작성** — `scripts/build_index.py`

```python
"""오프라인 인덱스 빌드: JSONL -> Chroma 영속 컬렉션."""
from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.embedding import KureEmbedder
from bible_search.indexer import build_index


def main() -> None:
    s = get_settings()
    verses = load_verses(s.data_path)
    print(f"loaded {len(verses)} verses from {s.data_path}")
    embedder = KureEmbedder(s.embedding_model)
    count = build_index(verses, embedder, s.chroma_path, s.chroma_collection)
    print(f"indexed {count} verses into {s.chroma_path}/{s.chroma_collection}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add src/bible_search/indexer.py scripts/build_index.py tests/test_indexer.py
git commit -m "feat: add persistent Chroma indexer and build CLI"
```

---

### Task 3: 서비스 팩토리

**Files:**
- Create: `src/bible_search/factory.py`
- Test: (Task 4의 API 테스트에서 간접 커버 — 별도 단위 테스트는 slow 모델 의존이라 생략)

**Interfaces:**
- Consumes: `Settings`, `load_verses`, `KiwiTokenizer`, `ExactMatcher`, `BM25Retriever`, `DenseRetriever`, `KureEmbedder`, chromadb.
- Produces:
  - `build_search_service(settings: Settings, embedder: Embedder | None = None) -> SearchService` — JSONL 로드 후 ExactMatcher·BM25를 메모리 구성, `PersistentClient`로 기존 컬렉션을 열어 DenseRetriever 구성, `SearchService` 반환. `embedder`를 주입하면 그것을 쓰고(테스트용 가짜), 없으면 `KureEmbedder`를 로드.

- [ ] **Step 1: 구현** — `src/bible_search/factory.py`

```python
import chromadb
from bible_search.config import Settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer
from bible_search.embedding import Embedder, KureEmbedder
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.search_service import SearchService


def build_search_service(settings: Settings,
                         embedder: Embedder | None = None) -> SearchService:
    verses = load_verses(settings.data_path)
    if embedder is None:
        embedder = KureEmbedder(settings.embedding_model)

    client = chromadb.PersistentClient(settings.chroma_path)
    collection = client.get_collection(settings.chroma_collection)

    exact = ExactMatcher(verses)
    bm25 = BM25Retriever(verses, KiwiTokenizer())
    dense = DenseRetriever(collection, verses, embedder,
                           threshold=settings.dense_threshold)
    return SearchService(exact, bm25, dense,
                         rrf_k=settings.rrf_k, max_results=settings.max_results)
```

- [ ] **Step 2: import 스모크 확인**

Run: `. .venv/bin/activate && python -c "from bible_search.factory import build_search_service; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/bible_search/factory.py
git commit -m "feat: add search service factory"
```

---

### Task 4: FastAPI 앱 + API 키 인증

**Files:**
- Create: `src/bible_search/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Settings`, `get_settings`, `build_search_service`, `SearchService`, `SearchResult`.
- Produces:
  - FastAPI 앱 `app`.
  - `GET /health` → `{"status": "ok"}` (인증 불필요).
  - `POST /search` (헤더 `X-API-Key` 필요) 요청 body `{"query": str}` → `{"query", "exact_matches": [...], "related_matches": [...]}`. 각 항목은 `{"id","book","chapter","verse","text","translation","score","source"}`.
  - 인증 실패 시 401. `app.state.service`에 `SearchService` 보관(테스트에서 주입 가능).
  - 헬퍼 `_serialize(result: SearchResult) -> dict`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_api.py`

```python
import numpy as np
import chromadb
import pytest
from fastapi.testclient import TestClient

from bible_search.config import Settings
from bible_search.retrievers.dense import add_verses_to_collection


class FakeEmbedder:
    VOCAB = ["여호와", "목자", "소망", "구원", "빛", "창조", "태초", "희망"]
    def encode(self, texts):
        vecs = []
        for t in texts:
            v = np.array([1.0 if w in t else 0.0 for w in self.VOCAB], dtype=np.float32)
            n = np.linalg.norm(v)
            vecs.append(v / n if n > 0 else v)
        return np.vstack(vecs)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # fixture 데이터를 임시 JSONL로 복사
    from pathlib import Path
    src = Path(__file__).parent / "data" / "verses_fixture.jsonl"
    data_path = tmp_path / "verses.jsonl"
    data_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    chroma_path = str(tmp_path / "chroma")

    monkeypatch.setenv("BIBLE_API_KEY", "testkey")
    monkeypatch.setenv("BIBLE_DATA_PATH", str(data_path))
    monkeypatch.setenv("BIBLE_CHROMA_PATH", chroma_path)
    monkeypatch.setenv("BIBLE_DENSE_THRESHOLD", "0.5")

    # 가짜 임베더로 인덱스 구축 후 서비스 조립
    from bible_search.data.loader import load_verses
    from bible_search.indexer import build_index
    from bible_search.factory import build_search_service
    settings = Settings()
    verses = load_verses(settings.data_path)
    build_index(verses, FakeEmbedder(), settings.chroma_path, settings.chroma_collection)
    service = build_search_service(settings, embedder=FakeEmbedder())

    from bible_search.api import app, get_settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.service = service
    return TestClient(app)


def test_health_no_auth(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_search_requires_api_key(client):
    r = client.post("/search", json={"query": "여호와"})
    assert r.status_code == 401


def test_search_wrong_api_key(client):
    r = client.post("/search", json={"query": "여호와"}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_search_returns_sections(client):
    r = client.post("/search", json={"query": "천지를 창조"},
                    headers={"X-API-Key": "testkey"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "천지를 창조"
    exact_ids = [m["id"] for m in body["exact_matches"]]
    assert "개역개정:창세기:1:1" in exact_ids
    assert "source" in body["exact_matches"][0]
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_api.py -q`
Expected: FAIL (`ModuleNotFoundError: bible_search.api`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/api.py`

```python
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from pydantic import BaseModel

from bible_search.config import Settings, get_settings
from bible_search.factory import build_search_service
from bible_search.models import SearchResult

app = FastAPI(title="Bible Hybrid Search")


class SearchRequest(BaseModel):
    query: str


def _serialize(r: SearchResult) -> dict:
    v = r.verse
    return {
        "id": v.id, "book": v.book, "chapter": v.chapter, "verse": v.verse,
        "text": v.text, "translation": v.translation,
        "score": r.score, "source": r.source,
    }


def _require_api_key(x_api_key: str | None, settings: Settings) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.on_event("startup")
def _startup() -> None:
    # app.state.service가 이미 주입된 경우(테스트) 재구성하지 않는다
    if not getattr(app.state, "service", None):
        app.state.service = build_search_service(get_settings())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/search")
def search(req: SearchRequest, request: Request,
           x_api_key: str | None = Header(default=None),
           settings: Settings = Depends(get_settings)) -> dict:
    _require_api_key(x_api_key, settings)
    resp = request.app.state.service.search(req.query)
    return {
        "query": req.query,
        "exact_matches": [_serialize(r) for r in resp.exact_matches],
        "related_matches": [_serialize(r) for r in resp.related_matches],
    }
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_api.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: 전체 테스트 실행**

Run: `pytest -q`
Expected: 모든 테스트 PASS (slow 제외).

- [ ] **Step 6: Commit**

```bash
git add src/bible_search/api.py tests/test_api.py
git commit -m "feat: add FastAPI app with API-key auth and search endpoint"
```

---

### Task 5: 성경 텍스트 확보 스크립트

**Files:**
- Create: `scripts/fetch_data.py`

**Interfaces:**
- Produces: `data/verses.jsonl` (정본 포맷). 스크립트는 소스에서 구절을 수집해 `Verse`와 동일한 스키마의 JSONL로 기록.

> **주의:** 실제 소스는 실행 시점에 확정한다(스펙 4절). 아래 절차를 따른다.

- [ ] **Step 1: 공개 텍스트 파일 탐색 (실행자 판단)**

먼저 공개된 개역개정/개역한글 등 성경 텍스트 데이터셋(공개 리포·데이터 포털)이 있는지 조사한다. 라이선스가 재배포·사용에 적합한지 반드시 확인한다. 적합한 파일을 찾으면 그 포맷을 정본 JSONL로 변환하는 파서를 이 스크립트에 구현한다.

- [ ] **Step 2: 공개 파일이 없으면 사용자 API로 수집**

공개 파일이 없거나 라이선스가 부적합하면, 사용자가 아는 성경 API로 전체 구절을 수집한다. API 키/엔드포인트는 환경변수로 받는다(하드코딩 금지). 요청은 rate limit을 지키고, 중단 시 이어받을 수 있게 책별로 저장한다.

- [ ] **Step 3: 정본 JSONL 기록 (공통)**

수집 결과를 `data/verses.jsonl`로 기록한다. 각 줄은 반드시 다음 스키마를 만족:
```json
{"id": "<translation>:<book>:<chapter>:<verse>", "book": "창세기", "chapter": 1, "verse": 1, "text": "...", "translation": "개역개정"}
```
`id`는 `translation:book:chapter:verse` 규칙으로 유일해야 한다.

- [ ] **Step 4: 로더로 무결성 검증**

Run: `. .venv/bin/activate && python -c "from bible_search.data.loader import load_verses; v=load_verses('data/verses.jsonl'); print(len(v), v[0])"`
Expected: 구절 수(성경 전체면 3만 내외)와 첫 구절이 정상 출력되고 로더 예외가 없어야 한다.

- [ ] **Step 5: Commit (스크립트만 — 데이터 파일은 커밋 금지)**

```bash
git add scripts/fetch_data.py
git commit -m "feat: add Bible text acquisition script"
```

---

### Task 6: 고어체 검증 / 임계값 튜닝 하니스

**Files:**
- Create: `scripts/evaluate.py`, `tests/data/eval_set.jsonl`

**Interfaces:**
- Consumes: 실제 인덱스(Task 2로 구축)와 실제 데이터(Task 5), `build_search_service`.
- Produces:
  - `tests/data/eval_set.jsonl` — 라벨 세트. 각 줄 `{"query": "현대어 질의", "expected_ids": ["<정답 구절 id>", ...]}`. 스펙 3.5대로 현대어↔고어체 쌍 20~30개.
  - `scripts/evaluate.py` — 주어진 임계값들(예: 0.8, 0.9)에 대해 eval_set의 recall@k / precision을 계산해 표로 출력. Kiwi 토큰화 샘플도 함께 출력해 어간 붕괴 여부를 육안 확인.

- [ ] **Step 1: 라벨 세트 초안 작성** — `tests/data/eval_set.jsonl` (예시 3줄, 실제로는 20~30줄로 확장)

```jsonl
{"query": "세상을 창조한 첫 순간", "expected_ids": ["개역개정:창세기:1:1"]}
{"query": "하나님을 기다리는 마음", "expected_ids": ["개역개정:시편:130:5"]}
{"query": "미래에 대한 희망과 소망", "expected_ids": ["개역개정:예레미야:29:11", "개역개정:로마서:8:24"]}
```

> 실제 `expected_ids`는 Task 5로 확보한 데이터의 실제 구절 id와 일치해야 한다.

- [ ] **Step 2: 평가 스크립트 작성** — `scripts/evaluate.py`

```python
"""고어체 검증 + Dense 임계값 튜닝 하니스."""
import json
from pathlib import Path
from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.tokenizer import KiwiTokenizer
from bible_search.factory import build_search_service

EVAL = Path("tests/data/eval_set.jsonl")


def load_eval():
    rows = []
    for line in EVAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def evaluate(threshold: float, rows) -> tuple[float, float]:
    s = get_settings()
    s = s.model_copy(update={"dense_threshold": threshold})
    service = build_search_service(s)
    hits = total_expected = total_returned = 0
    for row in rows:
        expected = set(row["expected_ids"])
        resp = service.search(row["query"])
        got = {m.verse.id for m in resp.exact_matches + resp.related_matches}
        hits += len(expected & got)
        total_expected += len(expected)
        total_returned += len(got)
    recall = hits / total_expected if total_expected else 0.0
    precision = hits / total_returned if total_returned else 0.0
    return recall, precision


def main() -> None:
    rows = load_eval()
    print("=== Kiwi 토큰화 샘플 (어간 붕괴 확인) ===")
    tok = KiwiTokenizer()
    for verse in load_verses(get_settings().data_path)[:5]:
        print(verse.text, "->", tok.tokenize(verse.text))
    print("\n=== 임계값별 recall/precision ===")
    for th in (0.8, 0.9):
        recall, precision = evaluate(th, rows)
        print(f"threshold={th}: recall={recall:.3f} precision={precision:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 실행 (실제 데이터·인덱스 필요)**

Run: `. .venv/bin/activate && python scripts/evaluate.py`
Expected: Kiwi 토큰화 샘플에서 "창조" 등 내용어 어간이 살아있고, 0.8/0.9 각각의 recall/precision 표가 출력된다. 결과를 보고 스펙 3.5에 따라 `BIBLE_DENSE_THRESHOLD` 기본값을 확정한다.

- [ ] **Step 4: 확정 임계값을 `.env.example`에 반영 후 Commit**

```bash
git add scripts/evaluate.py tests/data/eval_set.jsonl .env.example
git commit -m "feat: add archaic-Korean eval harness and threshold tuning"
```

---

### Task 7: Docker 배포

**Files:**
- Create: `Dockerfile`, `.dockerignore`

**Interfaces:**
- Produces: `docker build`로 만들어지는 이미지. 컨테이너 시작 시 `uvicorn`으로 API를 서빙하며, 시작 시 모델·인덱스를 1회 로드해 상주.

> **주의:** 이미지에는 코드만 넣고, 데이터(`data/`)·인덱스(`chroma/`)는 빌드 시점 상황에 따라 볼륨 마운트하거나 별도 빌드 단계에서 생성한다. 아래는 코드+런타임 기준이며, 인덱스는 컨테이너 기동 전에 `scripts/build_index.py`로 생성되어 마운트된다고 가정한다.

- [ ] **Step 1: `.dockerignore` 작성**

```dockerignore
.venv/
venv/
__pycache__/
.pytest_cache/
.git/
docs/
tests/
chroma/
data/
*.egg-info/
```

- [ ] **Step 2: `Dockerfile` 작성**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 빌드 도구(일부 의존성 컴파일용) 및 정리
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# 데이터/인덱스는 런타임에 볼륨으로 마운트 (/app/data, /app/chroma)
ENV BIBLE_DATA_PATH=/app/data/verses.jsonl \
    BIBLE_CHROMA_PATH=/app/chroma \
    HF_HOME=/app/models

EXPOSE 8000
CMD ["uvicorn", "bible_search.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: 빌드 확인**

Run: `cd /Users/fastview/Desktop/dontan-bible-retriever && docker build -t bible-search .`
Expected: 이미지 빌드 성공.

- [ ] **Step 4: 기동 스모크 확인 (데이터·인덱스 마운트, API 키 주입)**

Run:
```bash
docker run --rm -p 8000:8000 \
  -e BIBLE_API_KEY=testkey \
  -v "$PWD/data:/app/data" -v "$PWD/chroma:/app/chroma" \
  bible-search &
sleep 20 && curl -s localhost:8000/health
```
Expected: `{"status":"ok"}`. (모델 로드로 기동에 시간이 걸릴 수 있음.)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add Dockerfile for API deployment"
```

---

## Self-Review (작성자 체크 완료)

- **Spec coverage:** 데이터 확보(Task 5)·오프라인 인덱싱(Task 2)·FastAPI+API키 인증(Task 4)·설정/환경변수(Task 1)·시작 시 1회 로드 상주(Task 4 startup + factory)·고어체 검증 및 0.8/0.9 튜닝(Task 6)·Docker(Task 7) 모두 커버. 3단 검색 로직 자체는 Plan 1에서 완료.
- **Placeholder scan:** 코드가 필요한 스텝엔 실제 코드 포함. Task 5·6은 실제 외부 데이터에 의존하는 본질적 미결(소스·실제 id)이라 "실행자 판단" 절차와 검증 커맨드를 명시했고, 이는 스펙 9절의 의도된 미결 항목이다.
- **Type consistency:** `build_search_service(settings, embedder=None)`, `build_index(verses, embedder, chroma_path, collection_name)`, `Settings` 필드명, `SearchResponse.exact_matches/related_matches`가 Plan 1 및 태스크 간 일치. `app.state.service` 주입 규약이 startup 훅과 테스트에서 일관.

## 실행 순서 주의

1. **Plan 1 완료 후** 진행.
2. Task 1(설정) → Task 2(인덱서) → Task 3(팩토리) → Task 4(API)까지는 fixture/가짜 임베더로 완결 테스트 가능.
3. Task 5(데이터)는 실제 소스 확정이 필요하며, 완료 후 `scripts/build_index.py`로 실인덱스를 만들어야 Task 6(검증)·Task 7 스모크가 의미를 가진다.
