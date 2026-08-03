import Link from "next/link";
import { bibleVerses } from "@/data";

const RECENT_READING = { book: "창세기", chapter: 1 };
const VERSE_OF_THE_DAY = bibleVerses[0];

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <section>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
          안녕하세요
        </h1>
        <p className="mt-1 text-zinc-600 dark:text-zinc-400">
          오늘도 말씀과 함께 하루를 시작해보세요.
        </p>
      </section>

      <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
          최근 읽은 위치
        </h2>
        <p className="mt-2 text-lg font-medium text-zinc-900 dark:text-zinc-50">
          {RECENT_READING.book} {RECENT_READING.chapter}장
        </p>
        <Link
          href={`/read?book=${encodeURIComponent(RECENT_READING.book)}&chapter=${RECENT_READING.chapter}`}
          className="mt-3 inline-block rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-50 dark:text-black dark:hover:bg-zinc-200"
        >
          이어서 읽기
        </Link>
      </section>

      <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
          오늘의 말씀
        </h2>
        {VERSE_OF_THE_DAY && (
          <>
            <p className="mt-2 text-lg leading-relaxed text-zinc-900 dark:text-zinc-50">
              &ldquo;{VERSE_OF_THE_DAY.text}&rdquo;
            </p>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              {VERSE_OF_THE_DAY.book} {VERSE_OF_THE_DAY.chapter}장{" "}
              {VERSE_OF_THE_DAY.verse}절 ({VERSE_OF_THE_DAY.translation})
            </p>
          </>
        )}
      </section>

      <section className="grid grid-cols-2 gap-4">
        <Link
          href="/search"
          className="rounded-2xl border border-zinc-200 bg-white p-5 text-center font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:hover:bg-zinc-900"
        >
          말씀 검색
        </Link>
        <Link
          href="/bookmarks"
          className="rounded-2xl border border-zinc-200 bg-white p-5 text-center font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:hover:bg-zinc-900"
        >
          내 북마크
        </Link>
      </section>
    </main>
  );
}
