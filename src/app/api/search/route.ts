import { NextResponse } from "next/server";
import type { SearchRequest, SearchResponse, SearchResult } from "@/types/search";
import { findHighlightRanges } from "@/lib/highlight";

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

  const upstreamRes = await fetch(`${apiUrl}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify({ query }),
  });

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
