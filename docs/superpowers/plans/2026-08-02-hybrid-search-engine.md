# 성경 하이브리드 검색 엔진(코어) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 성경 구절을 대상으로 Exact/BM25/Dense 3종 검색과 RRF 병합을 수행하는, 작은 fixture로 완결 테스트 가능한 검색 엔진 라이브러리를 만든다.

**Architecture:** 각 리트리버는 `search(query) -> list[SearchResult]` 동일 인터페이스를 갖는 독립 단위다. `SearchService`가 Exact를 최상단에 두고 BM25·Dense를 RRF로 병합한 `related_matches`를 조립한다. 임베딩은 `Embedder` 프로토콜로 추상화해 단위 테스트에서는 가짜 임베더를, 실제 검색에는 KURE-v1을 주입한다(테스트 사이클을 빠르게 유지).

**Tech Stack:** Python 3.12, rank-bm25, kiwipiepy(Kiwi 형태소 분석), chromadb, sentence-transformers(KURE-v1), numpy, pytest.

## Global Constraints

- Python **3.12** 사용(로컬 확인됨: 3.12.2). src 레이아웃, 패키지명 `bible_search`, `pip install -e .`로 설치.
- 구절 데이터의 정본(canonical) 교환 포맷은 **JSONL**: 한 줄당 `{"id","book","chapter","verse","text","translation"}`.
- 모든 리트리버는 `Retriever` 프로토콜(`search(self, query: str) -> list[SearchResult]`)을 만족한다.
- 임베딩 벡터는 **L2 정규화**되어 코사인 유사도를 내적으로 계산할 수 있어야 한다.
- BM25는 매칭(score>0)되는 구절을 **개수 제한 없이** 반환한다(안전 상한은 선택적 `limit` 인자로만).
- Dense는 고정 top-k가 아니라 **코사인 유사도 임계값(threshold)** 이상만 반환한다.
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` 포함.

## File Structure

```
pyproject.toml                         # 프로젝트 메타 + 의존성
.gitignore
src/bible_search/
├── __init__.py
├── models.py                          # Verse, SearchResult
├── data/loader.py                     # load_verses(path) -> list[Verse]
├── tokenizer.py                       # KiwiTokenizer
├── retrievers/base.py                 # Retriever 프로토콜
├── retrievers/exact.py                # ExactMatcher
├── retrievers/bm25.py                 # BM25Retriever
├── retrievers/dense.py                # DenseRetriever
├── embedding.py                       # Embedder 프로토콜, KureEmbedder
├── fusion.py                          # reciprocal_rank_fusion()
└── search_service.py                  # SearchService, SearchResponse
tests/
├── conftest.py
├── data/verses_fixture.jsonl
├── test_loader.py
├── test_tokenizer.py
├── test_exact.py
├── test_bm25.py
├── test_dense.py
├── test_fusion.py
└── test_search_service.py
```

---

### Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/bible_search/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: 설치 가능한 `bible_search` 패키지, `pytest` 실행 환경.

- [ ] **Step 1: `pyproject.toml` 작성**

```toml
[project]
name = "bible-search"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "rank-bm25>=0.2.2",
    "kiwipiepy>=0.17",
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: `.gitignore` 작성**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
# 데이터/인덱스/모델 산출물 (Plan 2에서 생성)
data/*.jsonl
chroma/
.chroma/
models/
```

- [ ] **Step 3: 패키지 초기화 파일 생성**

`src/bible_search/__init__.py`:
```python
"""성경 하이브리드 검색 엔진."""
```

`tests/__init__.py`: (빈 파일)

- [ ] **Step 4: 가상환경 생성 및 설치**

Run:
```bash
cd /Users/fastview/Desktop/dontan-bible-retriever
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```
Expected: 설치 성공(의존성 다운로드에 수 분 소요될 수 있음).

- [ ] **Step 5: pytest 동작 확인**

Run: `. .venv/bin/activate && pytest -q`
Expected: `no tests ran` (에러 없이 수집 0건).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/bible_search/__init__.py tests/__init__.py
git commit -m "chore: scaffold bible_search package"
```

---

### Task 2: 데이터 모델

**Files:**
- Create: `src/bible_search/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Verse(id: str, book: str, chapter: int, verse: int, text: str, translation: str)` — frozen dataclass.
  - `SearchResult(verse: Verse, score: float, source: str)` — frozen dataclass. `source ∈ {"exact","bm25","dense","rrf"}`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_models.py`

```python
from bible_search.models import Verse, SearchResult

def test_verse_fields():
    v = Verse(id="개역개정:창세기:1:1", book="창세기", chapter=1, verse=1,
              text="태초에 하나님이 천지를 창조하시니라", translation="개역개정")
    assert v.book == "창세기"
    assert v.chapter == 1

def test_search_result_wraps_verse():
    v = Verse(id="x", book="창세기", chapter=1, verse=1, text="t", translation="개역개정")
    r = SearchResult(verse=v, score=0.5, source="bm25")
    assert r.verse is v
    assert r.source == "bm25"
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_models.py -q`
Expected: FAIL (`ModuleNotFoundError: bible_search.models`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/models.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Verse:
    id: str
    book: str
    chapter: int
    verse: int
    text: str
    translation: str

@dataclass(frozen=True)
class SearchResult:
    verse: Verse
    score: float
    source: str
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_models.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/models.py tests/test_models.py
git commit -m "feat: add Verse and SearchResult models"
```

---

### Task 3: 데이터 로더 + 테스트 fixture

**Files:**
- Create: `src/bible_search/data/__init__.py`, `src/bible_search/data/loader.py`, `tests/data/verses_fixture.jsonl`, `tests/conftest.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `Verse` (Task 2).
- Produces:
  - `load_verses(path: str | Path) -> list[Verse]` — JSONL 파일을 읽어 `Verse` 리스트 반환. 빈 줄 무시.
  - pytest fixture `verses` (conftest) — fixture JSONL을 로드한 `list[Verse]`.

- [ ] **Step 1: 테스트 fixture 데이터 작성** — `tests/data/verses_fixture.jsonl`

```jsonl
{"id": "개역개정:창세기:1:1", "book": "창세기", "chapter": 1, "verse": 1, "text": "태초에 하나님이 천지를 창조하시니라", "translation": "개역개정"}
{"id": "개역개정:창세기:1:3", "book": "창세기", "chapter": 1, "verse": 3, "text": "하나님이 이르시되 빛이 있으라 하시니 빛이 있었고", "translation": "개역개정"}
{"id": "개역개정:시편:23:1", "book": "시편", "chapter": 23, "verse": 1, "text": "여호와는 나의 목자시니 내게 부족함이 없으리로다", "translation": "개역개정"}
{"id": "개역개정:시편:130:5", "book": "시편", "chapter": 130, "verse": 5, "text": "나 곧 내 영혼은 여호와를 기다리며 나는 그의 말씀을 바라는도다", "translation": "개역개정"}
{"id": "개역개정:로마서:8:24", "book": "로마서", "chapter": 8, "verse": 24, "text": "우리가 소망으로 구원을 얻었으매 보이는 소망이 소망이 아니니", "translation": "개역개정"}
{"id": "개역개정:예레미야:29:11", "book": "예레미야", "chapter": 29, "verse": 11, "text": "너희를 향한 나의 생각은 평안이요 재앙이 아니니라 너희에게 미래와 희망을 주는 것이니라", "translation": "개역개정"}
{"id": "개역개정:요한복음:3:16", "book": "요한복음", "chapter": 3, "verse": 16, "text": "하나님이 세상을 이처럼 사랑하사 독생자를 주셨으니", "translation": "개역개정"}
{"id": "개역개정:이사야:40:31", "book": "이사야", "chapter": 40, "verse": 31, "text": "오직 여호와를 앙망하는 자는 새 힘을 얻으리니", "translation": "개역개정"}
```

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_loader.py`

```python
from pathlib import Path
from bible_search.data.loader import load_verses

FIXTURE = Path(__file__).parent / "data" / "verses_fixture.jsonl"

def test_load_verses_count():
    verses = load_verses(FIXTURE)
    assert len(verses) == 8

def test_load_verses_parses_fields():
    verses = load_verses(FIXTURE)
    first = verses[0]
    assert first.book == "창세기"
    assert first.chapter == 1
    assert first.verse == 1
    assert "천지를 창조하시니라" in first.text

def test_load_verses_ignores_blank_lines(tmp_path):
    p = tmp_path / "v.jsonl"
    p.write_text(
        '{"id":"a","book":"창세기","chapter":1,"verse":1,"text":"t","translation":"개역개정"}\n\n',
        encoding="utf-8",
    )
    assert len(load_verses(p)) == 1
```

- [ ] **Step 3: 실패 확인**

Run: `pytest tests/test_loader.py -q`
Expected: FAIL (`ModuleNotFoundError: bible_search.data.loader`).

- [ ] **Step 4: 최소 구현** — `src/bible_search/data/__init__.py` (빈 파일) 과 `src/bible_search/data/loader.py`

```python
import json
from pathlib import Path
from bible_search.models import Verse


def load_verses(path: str | Path) -> list[Verse]:
    verses: list[Verse] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            verses.append(
                Verse(
                    id=d["id"],
                    book=d["book"],
                    chapter=int(d["chapter"]),
                    verse=int(d["verse"]),
                    text=d["text"],
                    translation=d["translation"],
                )
            )
    return verses
```

- [ ] **Step 5: conftest fixture 작성** — `tests/conftest.py`

```python
from pathlib import Path
import pytest
from bible_search.data.loader import load_verses

FIXTURE = Path(__file__).parent / "data" / "verses_fixture.jsonl"

@pytest.fixture
def verses():
    return load_verses(FIXTURE)
```

- [ ] **Step 6: 통과 확인**

Run: `pytest tests/test_loader.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add src/bible_search/data tests/data/verses_fixture.jsonl tests/conftest.py tests/test_loader.py
git commit -m "feat: add JSONL verse loader and test fixture"
```

---

### Task 4: Kiwi 토크나이저

**Files:**
- Create: `src/bible_search/tokenizer.py`
- Test: `tests/test_tokenizer.py`

**Interfaces:**
- Produces:
  - `KiwiTokenizer()` — 생성 시 Kiwi 인스턴스 1개 보유.
  - `KiwiTokenizer.tokenize(self, text: str) -> list[str]` — 내용어(명사/동사/형용사/부사/외래어·한자·숫자/어근) 형태소의 `form`을 소문자로 반환. 조사·어미·기호는 제외.
  - 클래스 상수 `CONTENT_TAGS: frozenset[str]`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_tokenizer.py`

```python
from bible_search.tokenizer import KiwiTokenizer

def test_tokenize_extracts_content_stems():
    tok = KiwiTokenizer()
    tokens = tok.tokenize("태초에 하나님이 천지를 창조하시니라")
    # 조사(에,이,를)·어미(하시니라의 하/시/니라)는 빠지고 내용어 어간이 남는다
    assert "태초" in tokens
    assert "창조" in tokens
    assert "천지" in tokens
    # 조사는 포함되지 않아야 한다
    assert "를" not in tokens
    assert "에" not in tokens

def test_tokenize_query_matches_verse_stem():
    tok = KiwiTokenizer()
    q = set(tok.tokenize("태초 창조"))
    v = set(tok.tokenize("태초에 하나님이 천지를 창조하시니라"))
    # 질의 토큰이 모두 구절 토큰에 포함되어야 BM25 매칭이 성립
    assert q.issubset(v)
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_tokenizer.py -q`
Expected: FAIL (`ModuleNotFoundError: bible_search.tokenizer`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/tokenizer.py`

```python
from kiwipiepy import Kiwi


class KiwiTokenizer:
    # 내용어 품사만 유지: 명사류/용언류/부사/외래어·한자·숫자/어근
    CONTENT_TAGS = frozenset({
        "NNG", "NNP", "NNB", "NR", "NP",       # 명사류
        "VV", "VA", "VX", "VCP", "VCN",        # 용언류
        "MAG", "MAJ",                          # 부사류
        "SL", "SH", "SN",                      # 외래어/한자/숫자
        "XR",                                  # 어근
    })

    def __init__(self) -> None:
        self._kiwi = Kiwi()

    def tokenize(self, text: str) -> list[str]:
        tokens = self._kiwi.tokenize(text)
        return [t.form.lower() for t in tokens if t.tag in self.CONTENT_TAGS]
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_tokenizer.py -q`
Expected: PASS (2 passed). 만약 `창조`가 누락되어 실패하면, 실제 Kiwi 분석 결과를 출력해(`Kiwi().tokenize("창조하시니라")`) 어간이 어느 태그로 잡히는지 확인하고 `CONTENT_TAGS`를 조정한다(이 확인 자체가 스펙 3.5의 Kiwi 검증 항목이다).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/tokenizer.py tests/test_tokenizer.py
git commit -m "feat: add Kiwi content-word tokenizer"
```

---

### Task 5: Retriever 프로토콜 + Exact 매처

**Files:**
- Create: `src/bible_search/retrievers/__init__.py`, `src/bible_search/retrievers/base.py`, `src/bible_search/retrievers/exact.py`
- Test: `tests/test_exact.py`

**Interfaces:**
- Consumes: `Verse`, `SearchResult`.
- Produces:
  - `Retriever` (Protocol): `search(self, query: str) -> list[SearchResult]`.
  - `ExactMatcher(verses: list[Verse])` — 공백/문장부호를 제거해 정규화한 뒤 부분 문자열 포함 검사.
  - `ExactMatcher.search(query)` — 매칭 구절을 `source="exact"`, `score=1.0`으로 전부 반환(개수 제한 없음).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_exact.py`

```python
from bible_search.retrievers.exact import ExactMatcher

def test_exact_finds_contained_phrase(verses):
    m = ExactMatcher(verses)
    results = m.search("천지를 창조")
    ids = [r.verse.id for r in results]
    assert "개역개정:창세기:1:1" in ids
    assert all(r.source == "exact" for r in results)

def test_exact_ignores_whitespace_and_punctuation(verses):
    m = ExactMatcher(verses)
    # 공백/문장부호가 달라도 매칭되어야 한다
    assert m.search("천지 를  창조")
    assert m.search("천지를,창조")

def test_exact_no_match_returns_empty(verses):
    m = ExactMatcher(verses)
    assert m.search("존재하지않는구절ZZZ") == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_exact.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현**

`src/bible_search/retrievers/__init__.py`: (빈 파일)

`src/bible_search/retrievers/base.py`:
```python
from typing import Protocol
from bible_search.models import SearchResult


class Retriever(Protocol):
    def search(self, query: str) -> list[SearchResult]:
        ...
```

`src/bible_search/retrievers/exact.py`:
```python
import re
from bible_search.models import Verse, SearchResult

_STRIP = re.compile(r"[\s\W]+", re.UNICODE)


def _normalize(s: str) -> str:
    return _STRIP.sub("", s)


class ExactMatcher:
    def __init__(self, verses: list[Verse]) -> None:
        self._verses = verses
        self._norm = [(_normalize(v.text), v) for v in verses]

    def search(self, query: str) -> list[SearchResult]:
        q = _normalize(query)
        if not q:
            return []
        return [
            SearchResult(verse=v, score=1.0, source="exact")
            for norm_text, v in self._norm
            if q in norm_text
        ]
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_exact.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/retrievers/__init__.py src/bible_search/retrievers/base.py src/bible_search/retrievers/exact.py tests/test_exact.py
git commit -m "feat: add Retriever protocol and ExactMatcher"
```

---

### Task 6: BM25 리트리버

**Files:**
- Create: `src/bible_search/retrievers/bm25.py`
- Test: `tests/test_bm25.py`

**Interfaces:**
- Consumes: `Verse`, `SearchResult`, `KiwiTokenizer`.
- Produces:
  - `BM25Retriever(verses: list[Verse], tokenizer: KiwiTokenizer)` — 생성 시 전체 구절을 토큰화해 `rank_bm25.BM25Okapi` 인덱스 구성.
  - `BM25Retriever.search(self, query: str, limit: int | None = None) -> list[SearchResult]` — `score>0`인 구절만 점수 내림차순 반환, `source="bm25"`. `limit`은 선택적 안전 상한(기본 None=전부).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_bm25.py`

```python
from bible_search.tokenizer import KiwiTokenizer
from bible_search.retrievers.bm25 import BM25Retriever

def test_bm25_matches_stem_despite_archaic_ending(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    # "태초 창조" 질의가 "...창조하시니라"(고어체) 구절을 찾아낸다
    results = r.search("태초 창조")
    ids = [x.verse.id for x in results]
    assert "개역개정:창세기:1:1" in ids
    assert all(x.source == "bm25" for x in results)

def test_bm25_excludes_zero_score(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    results = r.search("여호와")
    # 매칭된 구절만(점수>0) 나와야 하고, 무관한 구절(창세기 1:1)은 없어야 한다
    ids = [x.verse.id for x in results]
    assert "개역개정:시편:23:1" in ids
    assert "개역개정:창세기:1:1" not in ids
    assert all(x.score > 0 for x in results)

def test_bm25_no_match_returns_empty(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    assert r.search("컴퓨터프로그래밍") == []

def test_bm25_limit_caps_results(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    results = r.search("여호와", limit=1)
    assert len(results) <= 1
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_bm25.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/retrievers/bm25.py`

```python
from rank_bm25 import BM25Okapi
from bible_search.models import Verse, SearchResult
from bible_search.tokenizer import KiwiTokenizer


class BM25Retriever:
    def __init__(self, verses: list[Verse], tokenizer: KiwiTokenizer) -> None:
        self._verses = verses
        self._tokenizer = tokenizer
        corpus = [tokenizer.tokenize(v.text) for v in verses]
        # rank_bm25는 빈 문서를 허용하지만, 전부 빈 코퍼스는 방어
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        if self._bm25 is None:
            return []
        q_tokens = self._tokenizer.tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        ranked = [
            SearchResult(verse=self._verses[i], score=float(s), source="bm25")
            for i, s in enumerate(scores)
            if s > 0
        ]
        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked if limit is None else ranked[:limit]
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_bm25.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/retrievers/bm25.py tests/test_bm25.py
git commit -m "feat: add BM25 retriever with score>0 filtering"
```

---

### Task 7: Embedder 프로토콜 + KURE 임베더

**Files:**
- Create: `src/bible_search/embedding.py`
- Test: `tests/test_embedding.py`

**Interfaces:**
- Produces:
  - `Embedder` (Protocol): `encode(self, texts: list[str]) -> np.ndarray` — shape `(n, dim)`, L2 정규화.
  - `KureEmbedder(model_name="nlpai-lab/KURE-v1", device: str | None = None)` — sentence-transformers로 로드, `encode`는 정규화 벡터 반환.
- 참고: KURE-v1 실제 로드 테스트는 무겁고 네트워크가 필요하므로 `@pytest.mark.slow`로 분리하고 기본 실행에서 제외한다. 단위 테스트는 이후 Task에서 가짜 임베더로 수행.

- [ ] **Step 1: pytest 마커 등록** — `pyproject.toml`의 `[tool.pytest.ini_options]`에 아래 추가

```toml
markers = ["slow: 실제 모델 로드 등 느린 테스트 (기본 제외: -m 'not slow')"]
addopts = "-m 'not slow'"
```

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_embedding.py`

```python
import numpy as np
import pytest
from bible_search.embedding import KureEmbedder

@pytest.mark.slow
def test_kure_embedder_normalized_shape():
    emb = KureEmbedder()
    vecs = emb.encode(["여호와는 나의 목자시니", "빛이 있으라"])
    assert vecs.shape[0] == 2
    # L2 정규화 확인 (norm ~ 1.0)
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
```

- [ ] **Step 3: 실패 확인 (slow 포함 실행)**

Run: `pytest tests/test_embedding.py -q -m slow`
Expected: FAIL (`ModuleNotFoundError: bible_search.embedding`).

- [ ] **Step 4: 최소 구현** — `src/bible_search/embedding.py`

```python
from typing import Protocol
import numpy as np


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        ...


class KureEmbedder:
    def __init__(self, model_name: str = "nlpai-lab/KURE-v1",
                 device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
```

- [ ] **Step 5: 통과 확인 (slow 실행)**

Run: `pytest tests/test_embedding.py -q -m slow`
Expected: PASS (1 passed). 최초 실행 시 KURE-v1 모델 다운로드(수 GB)로 시간이 걸림.

- [ ] **Step 6: 기본 실행에서 제외 확인**

Run: `pytest -q`
Expected: `test_embedding.py`의 slow 테스트가 deselected 되어 수집에서 빠짐(에러 없음).

- [ ] **Step 7: Commit**

```bash
git add src/bible_search/embedding.py tests/test_embedding.py pyproject.toml
git commit -m "feat: add Embedder protocol and KURE-v1 embedder"
```

---

### Task 8: Dense 리트리버 (Chroma + 임계값)

**Files:**
- Create: `src/bible_search/retrievers/dense.py`
- Test: `tests/test_dense.py`

**Interfaces:**
- Consumes: `Verse`, `SearchResult`, `Embedder`(프로토콜), chromadb Collection.
- Produces:
  - `DenseRetriever(collection, verses: list[Verse], embedder: Embedder, threshold: float = 0.8)` — `collection`은 코사인 거리(`hnsw:space=cosine`)로 생성된 Chroma 컬렉션(구절 id·임베딩이 이미 적재됨). `verses`는 id→Verse 매핑용.
  - `DenseRetriever.search(self, query: str) -> list[SearchResult]` — 코사인 유사도 = `1 - distance` 가 `threshold` 이상인 구절만 유사도 내림차순 반환, `source="dense"`.
  - 모듈 함수 `add_verses_to_collection(collection, verses, embedder) -> None` — 테스트/인덱서 공용으로, 구절을 임베딩해 컬렉션에 적재.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_dense.py`

```python
import numpy as np
import chromadb
import pytest
from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection


class FakeEmbedder:
    """토큰 집합을 고정 차원 멀티-핫 벡터로 인코딩하는 결정적 가짜 임베더."""
    VOCAB = ["여호와", "목자", "소망", "구원", "빛", "창조", "태초", "희망"]

    def encode(self, texts):
        vecs = []
        for t in texts:
            v = np.array([1.0 if w in t else 0.0 for w in self.VOCAB], dtype=np.float32)
            n = np.linalg.norm(v)
            vecs.append(v / n if n > 0 else v)
        return np.vstack(vecs)


@pytest.fixture
def dense(verses):
    client = chromadb.EphemeralClient()
    col = client.create_collection("t", metadata={"hnsw:space": "cosine"})
    emb = FakeEmbedder()
    add_verses_to_collection(col, verses, emb)
    return DenseRetriever(col, verses, emb, threshold=0.5)


def test_dense_returns_semantically_similar(dense):
    results = dense.search("여호와")
    ids = [r.verse.id for r in results]
    # "여호와"가 든 구절들이 임계값 이상으로 잡힌다
    assert "개역개정:시편:23:1" in ids
    assert all(r.source == "dense" for r in results)
    assert all(r.score >= 0.5 for r in results)


def test_dense_threshold_excludes_unrelated(verses):
    client = chromadb.EphemeralClient()
    col = client.create_collection("t2", metadata={"hnsw:space": "cosine"})
    emb = FakeEmbedder()
    add_verses_to_collection(col, verses, emb)
    r = DenseRetriever(col, verses, emb, threshold=0.99)
    # 임계값이 매우 높으면 무관한 질의는 결과가 비거나 극소수
    assert r.search("컴퓨터") == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_dense.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/retrievers/dense.py`

```python
from bible_search.models import Verse, SearchResult
from bible_search.embedding import Embedder


def add_verses_to_collection(collection, verses: list[Verse], embedder: Embedder) -> None:
    if not verses:
        return
    embeddings = embedder.encode([v.text for v in verses])
    collection.add(
        ids=[v.id for v in verses],
        embeddings=[e.tolist() for e in embeddings],
    )


class DenseRetriever:
    def __init__(self, collection, verses: list[Verse], embedder: Embedder,
                 threshold: float = 0.8) -> None:
        self._collection = collection
        self._embedder = embedder
        self._threshold = threshold
        self._by_id = {v.id: v for v in verses}

    def search(self, query: str) -> list[SearchResult]:
        q = self._embedder.encode([query])[0]
        n = self._collection.count()
        if n == 0:
            return []
        res = self._collection.query(
            query_embeddings=[q.tolist()],
            n_results=n,
        )
        ids = res["ids"][0]
        distances = res["distances"][0]
        out: list[SearchResult] = []
        for vid, dist in zip(ids, distances):
            sim = 1.0 - float(dist)
            if sim >= self._threshold and vid in self._by_id:
                out.append(SearchResult(verse=self._by_id[vid], score=sim, source="dense"))
        out.sort(key=lambda r: r.score, reverse=True)
        return out
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_dense.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/retrievers/dense.py tests/test_dense.py
git commit -m "feat: add Dense retriever with cosine threshold cutoff"
```

---

### Task 9: RRF 병합

**Files:**
- Create: `src/bible_search/fusion.py`
- Test: `tests/test_fusion.py`

**Interfaces:**
- Consumes: `SearchResult`.
- Produces:
  - `reciprocal_rank_fusion(result_lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]` — 각 리스트에서의 순위(0-based rank)로 `rrf_score = Σ 1/(k + rank + 1)`를 구절 id별 합산. 대표 `Verse`는 첫 등장 것을 사용, `source="rrf"`, `score=rrf_score`. rrf_score 내림차순 정렬 반환. 길이가 다른 리스트도 정상 처리.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_fusion.py`

```python
from bible_search.models import Verse, SearchResult
from bible_search.fusion import reciprocal_rank_fusion


def _v(i):
    return Verse(id=str(i), book="b", chapter=1, verse=i, text=f"t{i}", translation="개역개정")


def test_rrf_rewards_agreement():
    v1, v2, v3 = _v(1), _v(2), _v(3)
    list_a = [SearchResult(v1, 5.0, "bm25"), SearchResult(v2, 3.0, "bm25")]
    list_b = [SearchResult(v2, 0.9, "dense"), SearchResult(v3, 0.8, "dense")]
    fused = reciprocal_rank_fusion([list_a, list_b])
    # v2는 두 리스트 모두에 등장 -> 최상위
    assert fused[0].verse.id == "2"
    assert all(r.source == "rrf" for r in fused)


def test_rrf_handles_different_lengths():
    v1, v2, v3, v4 = _v(1), _v(2), _v(3), _v(4)
    long = [SearchResult(_v(i), 1.0, "bm25") for i in range(1, 5)]
    short = [SearchResult(v4, 0.9, "dense")]
    fused = reciprocal_rank_fusion([long, short])
    ids = [r.verse.id for r in fused]
    assert set(ids) == {"1", "2", "3", "4"}
    # v4는 양쪽에 등장 -> 1위
    assert fused[0].verse.id == "4"


def test_rrf_empty_input():
    assert reciprocal_rank_fusion([[], []]) == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_fusion.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/fusion.py`

```python
from bible_search.models import SearchResult


def reciprocal_rank_fusion(result_lists: list[list[SearchResult]],
                           k: int = 60) -> list[SearchResult]:
    scores: dict[str, float] = {}
    verses: dict[str, object] = {}
    for results in result_lists:
        for rank, r in enumerate(results):
            vid = r.verse.id
            scores[vid] = scores.get(vid, 0.0) + 1.0 / (k + rank + 1)
            verses.setdefault(vid, r.verse)
    fused = [
        SearchResult(verse=verses[vid], score=score, source="rrf")
        for vid, score in scores.items()
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_fusion.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bible_search/fusion.py tests/test_fusion.py
git commit -m "feat: add reciprocal rank fusion"
```

---

### Task 10: 검색 서비스 (3단 조립)

**Files:**
- Create: `src/bible_search/search_service.py`
- Test: `tests/test_search_service.py`

**Interfaces:**
- Consumes: `ExactMatcher`, `BM25Retriever`, `DenseRetriever`, `reciprocal_rank_fusion`, `SearchResult`.
- Produces:
  - `SearchResponse(exact_matches: list[SearchResult], related_matches: list[SearchResult])` — frozen dataclass.
  - `SearchService(exact, bm25, dense, rrf_k: int = 60, max_results: int = 500)`.
  - `SearchService.search(self, query: str) -> SearchResponse` — Exact 결과 전부를 `exact_matches`로, BM25∪Dense를 RRF로 병합하되 **exact에 이미 든 구절 id는 제외**하고 상한 `max_results`까지 잘라 `related_matches`로 반환.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_search_service.py`

```python
import chromadb
import numpy as np
from bible_search.tokenizer import KiwiTokenizer
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever, add_verses_to_collection
from bible_search.search_service import SearchService, SearchResponse


class FakeEmbedder:
    VOCAB = ["여호와", "목자", "소망", "구원", "빛", "창조", "태초", "희망"]
    def encode(self, texts):
        vecs = []
        for t in texts:
            v = np.array([1.0 if w in t else 0.0 for w in self.VOCAB], dtype=np.float32)
            n = np.linalg.norm(v)
            vecs.append(v / n if n > 0 else v)
        return np.vstack(vecs)


def _service(verses, threshold=0.5):
    client = chromadb.EphemeralClient()
    col = client.create_collection("s", metadata={"hnsw:space": "cosine"})
    emb = FakeEmbedder()
    add_verses_to_collection(col, verses, emb)
    return SearchService(
        exact=ExactMatcher(verses),
        bm25=BM25Retriever(verses, KiwiTokenizer()),
        dense=DenseRetriever(col, verses, emb, threshold=threshold),
    )


def test_search_returns_response_shape(verses):
    svc = _service(verses)
    resp = svc.search("여호와")
    assert isinstance(resp, SearchResponse)
    assert isinstance(resp.exact_matches, list)
    assert isinstance(resp.related_matches, list)


def test_exact_hit_appears_in_exact_section(verses):
    svc = _service(verses)
    resp = svc.search("천지를 창조")
    exact_ids = [r.verse.id for r in resp.exact_matches]
    assert "개역개정:창세기:1:1" in exact_ids


def test_related_excludes_exact_ids(verses):
    svc = _service(verses)
    resp = svc.search("여호와는 나의 목자")
    exact_ids = {r.verse.id for r in resp.exact_matches}
    related_ids = {r.verse.id for r in resp.related_matches}
    assert exact_ids  # exact 매칭이 있고
    assert exact_ids.isdisjoint(related_ids)  # related에는 중복되지 않는다


def test_max_results_caps_related(verses):
    svc = _service(verses)
    svc._max_results = 1
    resp = svc.search("여호와")
    assert len(resp.related_matches) <= 1
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_search_service.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 최소 구현** — `src/bible_search/search_service.py`

```python
from dataclasses import dataclass
from bible_search.models import SearchResult
from bible_search.retrievers.exact import ExactMatcher
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.dense import DenseRetriever
from bible_search.fusion import reciprocal_rank_fusion


@dataclass(frozen=True)
class SearchResponse:
    exact_matches: list[SearchResult]
    related_matches: list[SearchResult]


class SearchService:
    def __init__(self, exact: ExactMatcher, bm25: BM25Retriever, dense: DenseRetriever,
                 rrf_k: int = 60, max_results: int = 500) -> None:
        self._exact = exact
        self._bm25 = bm25
        self._dense = dense
        self._rrf_k = rrf_k
        self._max_results = max_results

    def search(self, query: str) -> SearchResponse:
        exact = self._exact.search(query)
        exact_ids = {r.verse.id for r in exact}

        bm25 = self._bm25.search(query)
        dense = self._dense.search(query)
        fused = reciprocal_rank_fusion([bm25, dense], k=self._rrf_k)

        related = [r for r in fused if r.verse.id not in exact_ids][: self._max_results]
        return SearchResponse(exact_matches=exact, related_matches=related)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_search_service.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: 전체 테스트 실행**

Run: `pytest -q`
Expected: 모든 테스트 PASS (slow 제외).

- [ ] **Step 6: Commit**

```bash
git add src/bible_search/search_service.py tests/test_search_service.py
git commit -m "feat: add SearchService assembling exact + RRF(bm25,dense)"
```

---

## Self-Review (작성자 체크 완료)

- **Spec coverage:** Exact(Task 5)·BM25/Kiwi(Task 4,6)·Dense/KURE/Chroma/임계값(Task 7,8)·RRF(Task 9)·3단 조립과 exact/related 분리·max_results 상한(Task 10)·JSONL 정본 포맷(Task 3) 모두 태스크로 커버. 데이터 확보·API·인증·Docker·고어체 평가 하니스는 **Plan 2** 범위.
- **Placeholder scan:** TODO/TBD 없음. 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `search()` 시그니처, `SearchResult(verse, score, source)`, `add_verses_to_collection` 이름/인자, `SearchResponse` 필드명(`exact_matches`/`related_matches`)이 Task 간 일치.

## 실행 후 산출물

Plan 1 완료 시: fixture 8개 구절로 3단 하이브리드 검색이 동작·테스트되는 `bible_search` 라이브러리. 실제 성경 데이터·API·배포는 Plan 2에서 이 라이브러리를 그대로 사용해 붙인다.
