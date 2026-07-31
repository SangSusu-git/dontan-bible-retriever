import type {
  SearchAdapter,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from "@/types/search";
import { bibleVerses } from "@/data";

function findHighlightRanges(text: string, query: string): [number, number][] {
  if (!query) return [];

  const ranges: [number, number][] = [];
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();

  let fromIndex = 0;
  while (fromIndex <= lowerText.length) {
    const index = lowerText.indexOf(lowerQuery, fromIndex);
    if (index === -1) break;
    ranges.push([index, index + query.length]);
    fromIndex = index + query.length;
  }

  return ranges;
}

/**
 * Mock 검색 구현.
 * 실제 검색 엔진(형태소 분석/임베딩 등)이 준비되면 이 함수의 내부 구현만
 * 동일한 시그니처로 교체하면 된다. 호출부(검색 화면)는 이 함수의 존재만 알고 있다.
 */
export async function search(request: SearchRequest): Promise<SearchResponse> {
  const query = request.query.trim();

  if (!query) {
    return { results: [], totalCount: 0 };
  }

  const matched: SearchResult[] = bibleVerses
    .filter((verse) => !request.translation || verse.translation === request.translation)
    .filter((verse) => !request.bookFilter || request.bookFilter.includes(verse.book))
    .filter((verse) => verse.text.includes(query))
    .map((verse) => ({
      book: verse.book,
      chapter: verse.chapter,
      verse: verse.verse,
      text: verse.text,
      highlight: findHighlightRanges(verse.text, query),
    }));

  const results =
    typeof request.limit === "number" ? matched.slice(0, request.limit) : matched;

  return { results, totalCount: matched.length };
}

export const mockSearchAdapter: SearchAdapter = { search };
