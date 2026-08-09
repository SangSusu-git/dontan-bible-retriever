import { NextResponse } from "next/server";
import type { SearchRequest, SearchResponse, SearchResult } from "@/types/search";
import { findHighlightRanges } from "@/lib/highlight";

// 검색 엔진(Render 무료 티어)은 15분 유휴 후 절전되어, 깨어나는 첫 요청이
// 30~60초 걸릴 수 있다. Vercel 서버리스 함수의 기본 실행 제한(짧음)에
// 걸리지 않도록 최대 실행 시간을 60초로 늘린다.
export const maxDuration = 60;

// 업스트림 호출 자체도 같은 이유로 넉넉히 기다리되, 상한은 둔다.
const UPSTREAM_TIMEOUT_MS = 55_000;

interface HybridSearchMatch {
  book: string;
  chapter: number;
  verse: number;
  text: string;
  translation: string;
}

interface HybridSearchResponse {
  query: string;
  exact_matches: HybridSearchMatch[];
  related_matches: HybridSearchMatch[];
}

export async function POST(request: Request) {
  const body = (await request.json()) as SearchRequest;
  const query = body.query?.trim() ?? "";

  if (!query) {
    return NextResponse.json<SearchResponse>({ results: [], totalCount: 0 });
  }

  const apiUrl = process.env.BIBLE_SEARCH_API_URL;
  const apiKey = process.env.BIBLE_SEARCH_API_KEY;

  if (!apiUrl || !apiKey) {
    return NextResponse.json(
      { error: "BIBLE_SEARCH_API_URL / BIBLE_SEARCH_API_KEY 환경변수가 설정되지 않았습니다." },
      { status: 500 }
    );
  }

  let upstreamRes: Response;
  try {
    upstreamRes = await fetch(`${apiUrl}/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
      },
      body: JSON.stringify({ query }),
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch {
    // 네트워크 실패 또는 절전에서 깨어나다 시간 초과된 경우
    return NextResponse.json(
      { error: "검색 서버가 응답하지 않습니다. 절전에서 깨어나는 중일 수 있으니 잠시 후 다시 시도해주세요." },
      { status: 504 }
    );
  }

  if (!upstreamRes.ok) {
    return NextResponse.json(
      { error: `검색 서버 오류 (${upstreamRes.status})` },
      { status: 502 }
    );
  }

  const upstream = (await upstreamRes.json()) as HybridSearchResponse;

  const matches = [...upstream.exact_matches, ...upstream.related_matches]
    .filter((m) => !body.translation || m.translation === body.translation)
    .filter((m) => !body.bookFilter || body.bookFilter.includes(m.book));

  const results: SearchResult[] = matches.map((m) => ({
    book: m.book,
    chapter: m.chapter,
    verse: m.verse,
    text: m.text,
    highlight: findHighlightRanges(m.text, query),
  }));

  const limited =
    typeof body.limit === "number" ? results.slice(0, body.limit) : results;

  return NextResponse.json<SearchResponse>({
    results: limited,
    totalCount: results.length,
  });
}
