# dontan-bible-retriever

성경 본문을 읽고, 북마크하고, 검색할 수 있는 Next.js(App Router, TypeScript) 기반 웹 성경 앱입니다.

## 브랜치 구조

`app` 브랜치는 성경 앱(웹) 작업을 모으는 통합 브랜치이며, 기능별 하위 브랜치(`app-*`)를
PR로 받아 병합한다. `main`으로의 병합은 별도 승인 후 진행한다.

| 브랜치 | 내용 |
| --- | --- |
| `main` | 배포 기준 브랜치 (아직 `app` 병합 전) |
| `app` | 성경 앱 작업을 모으는 통합 브랜치 |
| `app-db` | Next.js 프로젝트 스캐폴딩, 폴더 구조, 공통 타입, 개역한글 창세기 1장 샘플 데이터 |
| `app-search-adapter` | 검색 인터페이스(`SearchAdapter`) 및 mock `search()` 구현 |
| `app-home` | 홈 화면 레이아웃(최근 읽은 위치, 오늘의 말씀, 바로가기) 및 공용 NavBar |
| `app-read` | 읽기 화면(책/장 선택 UI, 절 단위 본문 표시) |
| `app-search-screen` | 검색 화면(SearchBar, 결과 목록) — searchAdapter의 mock `search()`에 연동 |
| `app-bookmarks` | 북마크 화면 — `useBookmarks` 훅으로 localStorage에 저장/조회/삭제 |
| `app-readme` | README에 검색 엔진 연동 방법 / 성경 데이터 출처 문서화 |

이 표는 브랜치를 새로 푸시할 때마다 갱신한다.

## Getting Started

개발 서버 실행:

\`\`\`bash
npm run dev
\`\`\`

[http://localhost:3000](http://localhost:3000) 에서 결과를 확인할 수 있습니다.

## 검색 엔진 연동 방법

검색 기능은 [`src/types/search.ts`](src/types/search.ts)에 정의된 `SearchRequest` /
`SearchResponse` / `SearchAdapter` 인터페이스로 화면과 완전히 분리되어 있습니다.
현재는 [`src/services/search/searchAdapter.ts`](src/services/search/searchAdapter.ts)에
샘플 데이터를 문자열 포함 여부로 필터링하는 mock `search()` 함수만 들어있습니다.

실제 검색 엔진을 연동하려면:

1. `searchAdapter.ts`의 `search(request: SearchRequest): Promise<SearchResponse>`
   함수 **내부 구현만** 실제 검색 엔진 호출(API fetch 등)로 교체합니다. 함수 시그니처와
   반환 타입(`SearchResponse`)은 그대로 유지해야 합니다.
2. 화면(`src/app/search/page.tsx` 등)은 이 함수의 시그니처만 알고 있으므로, 위 교체만으로
   별도 수정 없이 그대로 동작합니다.
3. 필요하다면 `SearchRequest`/`SearchResult`에 optional 필드를 추가하는 것은 가능하지만,
   기존 필드를 변경/삭제할 경우 화면 쪽 사용처도 함께 확인해야 합니다.

## 성경 데이터 출처

현재 `src/data/`의 샘플 데이터(창세기 1장)는 **개역한글** 번역입니다. 개역한글은
저작권이 만료되어 자유롭게 사용할 수 있는 번역본입니다.

향후 **개역개정** 등 대한성서공회가 저작권을 보유한 번역본을 추가하려면, 사전에
대한성서공회의 사용 허가를 받아야 합니다. `BibleVerse` 타입(`src/types/bible.ts`)에
`translation` 필드를 두어, 번역본별 데이터를 손쉽게 이어 붙일 수 있도록 설계했습니다
(`src/data/index.ts`의 `bibleVerses` 배열 참고).
