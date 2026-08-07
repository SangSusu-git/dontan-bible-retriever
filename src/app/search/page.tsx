"use client";

import { useState, useTransition } from "react";
import SearchBar from "@/components/SearchBar";
import SearchResultItem from "@/components/SearchResultItem";
import { search } from "@/services/search/searchAdapter";
import type { SearchResponse } from "@/types/search";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit() {
    setHasSearched(true);
    setError(null);
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
      }
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">말씀 검색</h1>

      <SearchBar value={query} onChange={setQuery} onSubmit={handleSubmit} isLoading={isPending} />

      {error && (
        <p
          role="alert"
          className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {hasSearched && !error && response && (
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
      )}
    </main>
  );
}
