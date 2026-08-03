"use client";

import { useRouter } from "next/navigation";
import { BOOKS } from "@/data/books";

interface BookChapterSelectorProps {
  book: string;
  chapter: number;
}

export default function BookChapterSelector({ book, chapter }: BookChapterSelectorProps) {
  const router = useRouter();
  const selectedBook = BOOKS.find((b) => b.name === book) ?? BOOKS[0];

  function navigate(nextBook: string, nextChapter: number) {
    router.push(`/read?book=${encodeURIComponent(nextBook)}&chapter=${nextChapter}`);
  }

  return (
    <div className="flex gap-2">
      <select
        value={selectedBook.name}
        onChange={(e) => navigate(e.target.value, 1)}
        className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      >
        {BOOKS.map((b) => (
          <option key={b.name} value={b.name}>
            {b.name}
          </option>
        ))}
      </select>
      <select
        value={chapter}
        onChange={(e) => navigate(selectedBook.name, Number(e.target.value))}
        className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      >
        {Array.from({ length: selectedBook.chapterCount }, (_, i) => i + 1).map((c) => (
          <option key={c} value={c}>
            {c}장
          </option>
        ))}
      </select>
    </div>
  );
}
