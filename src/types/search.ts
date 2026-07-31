/**
 * 검색 엔진 연동을 위한 공통 인터페이스.
 * 이 타입들은 searchAdapter.ts 의 mock 구현과 실제 검색 엔진 구현이 동일하게 따라야 하는 계약입니다.
 * 필드를 변경해야 한다면 mock/실제 구현 양쪽과 이 타입을 사용하는 UI 컴포넌트에 영향이 없는지 확인하세요.
 */

export interface SearchRequest {
  query: string;
  translation?: string;
  bookFilter?: string[];
  limit?: number;
}

export interface SearchResult {
  book: string;
  chapter: number;
  verse: number;
  text: string;
  highlight?: [number, number][];
}

export interface SearchResponse {
  results: SearchResult[];
  totalCount: number;
}

/**
 * 검색 엔진 어댑터 계약.
 * 실제 검색 엔진을 연동할 때는 이 인터페이스를 구현하는 객체(또는 이 시그니처를 따르는 search 함수)를 제공하면 됩니다.
 */
export interface SearchAdapter {
  search(request: SearchRequest): Promise<SearchResponse>;
}
