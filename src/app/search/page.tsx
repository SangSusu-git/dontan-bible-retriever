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
  const [isPending, startTransition] = useTransition();

  function handleSubmit() {
    setHasSearched(true);
    startTransition(async () => {
      const result = await search({ query });
      setResponse(result);
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">말씀 검색</h1>

      <SearchBar value={query} onChange={setQuery} onSubmit={handleSubmit} isLoading={isPending} />

      {hasSearched && response && (
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
