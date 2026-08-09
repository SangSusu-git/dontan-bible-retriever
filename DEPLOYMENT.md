# 배포 가이드 (Vercel)

이 저장소의 `main` 브랜치는 **Next.js 성경 앱**입니다. 검색 기능은 별도로 배포된
검색 API(Render)를 호출하므로, 이 앱은 **환경변수 2개만 설정하면** 어디에든 배포할 수 있습니다.

```
[Vercel] 이 앱 (main)  ──환경변수로 연결──▶  [Render] 검색 API (이미 가동 중)
```

## 필요한 것

| 항목 | 값 |
|---|---|
| 배포 대상 브랜치 | `main` |
| `BIBLE_SEARCH_API_URL` | `https://bible-search-api-ygj1.onrender.com` |
| `BIBLE_SEARCH_API_KEY` | 관리자에게 별도로 받으세요 (저장소에는 없음) |

## Vercel 배포 순서 (약 10분)

1. https://vercel.com 접속 → GitHub 계정으로 로그인
2. **Add New… → Project** → `SangSusu-git/dontan-bible-retriever` 저장소 **Import**
   - 저장소가 목록에 없으면 "Adjust GitHub App Permissions"로 접근 권한 부여
3. 설정 화면에서:
   - **Branch**: `main` (기본값 그대로)
   - **Framework Preset**: Next.js (자동 감지됨)
   - **Environment Variables**에 위 표의 2개 입력
4. **Deploy** 클릭 → 빌드 완료 후 `https://<프로젝트명>.vercel.app` 주소 발급

## 배포 후 확인

1. 발급된 주소 접속 → 홈 화면이 뜨는지
2. **검색** 탭 → `사랑은 오래 참고` 검색 → 고린도전서 13:4가 최상단에 나오는지
3. 안 나오고 에러 문구가 보이면 ↓ 문제 해결 참고

## 꼭 알아둘 것: 검색 서버의 절전 (무료 호스팅 특성)

- 검색 API는 **15분간 사용이 없으면 절전**되며, 다음 첫 검색이 **30~60초** 걸립니다.
- 앱은 이 상황을 처리하도록 되어 있습니다:
  - 서버 라우트가 최대 60초 대기 (`maxDuration = 60`, `src/app/api/search/route.ts`)
  - 시간 초과 시 사용자에게 "잠시 후 다시 시도" 안내 표시
- 첫 검색이 오래 걸리다 실패하면 **한 번 더 검색**하면 됩니다 (서버가 깨어난 상태).

## 문제 해결

| 증상 | 원인/조치 |
|---|---|
| 검색 시 "환경변수가 설정되지 않았습니다" | Vercel 프로젝트 설정 → Environment Variables에 2개 값 확인 후 **Redeploy** |
| 검색 시 "검색 서버 오류 (401)" | `BIBLE_SEARCH_API_KEY` 값이 틀림 — 관리자에게 재확인 |
| 첫 검색만 실패, 재시도하면 됨 | 정상 (절전에서 깨어나는 중) |
| 계속 5xx | 검색 API 상태 확인: `curl https://bible-search-api-ygj1.onrender.com/health` |

## 로컬에서 돌려보기

```bash
npm install
cp .env.example .env.local   # BIBLE_SEARCH_API_KEY를 실제 키로 수정
npm run dev                  # http://localhost:3000
```
