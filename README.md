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

이 표는 브랜치를 새로 푸시할 때마다 갱신한다.

## Getting Started

개발 서버 실행:

\`\`\`bash
npm run dev
\`\`\`

[http://localhost:3000](http://localhost:3000) 에서 결과를 확인할 수 있습니다.