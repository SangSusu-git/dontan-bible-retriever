"use client";

import { bookmarkId, useBookmarks } from "@/hooks/useBookmarks";
import { bibleVerses } from "@/data";

export default function BookmarksPage() {
  const { bookmarks, addBookmark, removeBookmark, isBookmarked } = useBookmarks();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-8">
      <section>
        <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">내 북마크</h1>
        {bookmarks.length === 0 ? (
          <p className="mt-4 rounded-2xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
            아직 북마크한 말씀이 없습니다.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {bookmarks.map((bookmark) => (
              <li
                key={bookmark.id}
                className="flex items-start justify-between gap-3 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
              >
                <div>
                  <p className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
                    {bookmark.book} {bookmark.chapter}장 {bookmark.verse}절 (
                    {bookmark.translation})
                  </p>
                  <p className="mt-1 leading-relaxed text-zinc-900 dark:text-zinc-50">
                    {bookmark.text}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeBookmark(bookmark.id)}
                  className="shrink-0 rounded-full border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
                >
                  삭제
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
          샘플 본문에서 추가 (창세기 1장)
        </h2>
        <ul className="mt-3 flex flex-col gap-2">
          {bibleVerses.map((verse) => {
            const id = bookmarkId(verse);
            const bookmarked = isBookmarked(id);
            return (
              <li
                key={id}
                className="flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-2 dark:border-zinc-800 dark:bg-zinc-950"
              >
                <p className="truncate text-sm text-zinc-700 dark:text-zinc-300">
                  <span className="mr-2 font-semibold text-zinc-400 dark:text-zinc-500">
                    {verse.verse}
                  </span>
                  {verse.text}
                </p>
                <button
                  type="button"
                  onClick={() =>
                    bookmarked ? removeBookmark(id) : addBookmark(verse)
                  }
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
        </ul>
      </section>
    </main>
  );
}
