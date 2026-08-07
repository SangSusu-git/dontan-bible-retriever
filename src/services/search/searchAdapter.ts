import type { SearchAdapter, SearchRequest, SearchResponse } from "@/types/search";

/**
 * 하이브리드 검색 API 연동 구현.
 * 브라우저는 이 함수만 호출하고, 실제 검색 서버 호출과 API 키 처리는
 * 서버 라우트(src/app/api/search/route.ts)에서 담당한다.
 * 화면은 이 함수의 시그니처만 알고 있으므로, 내부 구현이 바뀌어도 호출부는 그대로 둔다.
 */
export async function search(request: SearchRequest): Promise<SearchResponse> {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    throw new Error(`검색에 실패했습니다 (${res.status})`);
  }

  return (await res.json()) as SearchResponse;
}

export const searchAdapter: SearchAdapter = { search };
