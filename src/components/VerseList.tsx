"use client";

import type { BibleVerse } from "@/types/bible";
import { bookmarkId, useBookmarks } from "@/hooks/useBookmarks";

interface VerseListProps {
  verses: BibleVerse[];
}

export default function VerseList({ verses }: VerseListProps) {
  const { addBookmark, removeBookmark, isBookmarked } = useBookmarks();

  if (verses.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        아직 이 장의 데이터가 없습니다.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {verses.map((verse) => {
        const id = bookmarkId(verse);
        const bookmarked = isBookmarked(id);
        return (
          <li key={verse.verse} className="flex items-start gap-3 leading-relaxed">
            <span className="mt-0.5 shrink-0 text-sm font-semibold text-zinc-400 dark:text-zinc-500">
              {verse.verse}
            </span>
            <span className="flex-1 text-zinc-900 dark:text-zinc-50">{verse.text}</span>
            <button
              type="button"
              onClick={() => (bookmarked ? removeBookmark(id) : addBookmark(verse))}
              className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                bookmarked
                  ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-black"
                  : "border border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
              }`}
            >
              {bookmarked ? "북마크됨" : "북마크"}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
