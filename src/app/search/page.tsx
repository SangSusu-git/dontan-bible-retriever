"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import SearchBar from "@/components/SearchBar";
import SearchResultItem from "@/components/SearchResultItem";
import { search } from "@/services/search/searchAdapter";
import type { SearchResponse } from "@/types/search";

const SLOW_RESPONSE_NOTICE_DELAY_MS = 2000;

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [showSlowNotice, setShowSlowNotice] = useState(false);
  const slowNoticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (slowNoticeTimer.current) clearTimeout(slowNoticeTimer.current);
    };
  }, []);

  function handleSubmit() {
    setHasSearched(true);
    setError(null);
    setShowSlowNotice(false);
    slowNoticeTimer.current = setTimeout(() => {
      setShowSlowNotice(true);
    }, SLOW_RESPONSE_NOTICE_DELAY_MS);

    startTransition(async () => {
      try {
        const result = await search({ query });
        setResponse(result);
      } catch {
        // 검색 서버(무료 호스팅)가 절전에서 깨어나는 30~60초 동안은
        // 요청이 실패할 수 있다 — 조용히 멈추지 말고 재시도를 안내한다.
        setResponse(null);
        setError(
          "검색에 실패했습니다. 서버가 깨어나는 중일 수 있으니 잠시 후 다시 시도해주세요."
        );
      } finally {
        if (slowNoticeTimer.current) clearTimeout(slowNoticeTimer.current);
        setShowSlowNotice(false);
      }
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">말씀 검색</h1>

      <SearchBar value={query} onChange={setQuery} onSubmit={handleSubmit} isLoading={isPending} />

      {showSlowNotice && (
        <div className="fixed left-1/2 top-4 z-50 -translate-x-1/2 rounded-full bg-amber-100 px-4 py-2 text-sm font-medium text-amber-800 shadow-lg ring-1 ring-amber-200 dark:bg-amber-900/80 dark:text-amber-100 dark:ring-amber-800">
          🐢 서버를 깨우느라 응답이 조금 느려요~ 조금만 기다려 주세요!
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {isPending ? (
        <div className="flex flex-col items-center gap-3 py-10 text-sm text-zinc-500 dark:text-zinc-400">
          <span className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-200 border-t-zinc-500 dark:border-zinc-700 dark:border-t-zinc-300" />
          검색 중이에요...
        </div>
      ) : (
        hasSearched &&
        !error &&
        response && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              총 {response.totalCount}건
            </p>
            {response.results.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                검색 결과가 없습니다.
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {response.results.map((result) => (
                  <SearchResultItem
                    key={`${result.book}-${result.chapter}-${result.verse}`}
                    result={result}
                  />
                ))}
              </ul>
            )}
          </div>
        )
      )}
    </main>
  );
}
