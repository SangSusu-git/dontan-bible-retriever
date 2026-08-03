import BookChapterSelector from "@/components/BookChapterSelector";
import VerseList from "@/components/VerseList";
import { getChapterVerses } from "@/data";

interface ReadPageProps {
  searchParams: Promise<{ book?: string; chapter?: string }>;
}

export default async function ReadPage({ searchParams }: ReadPageProps) {
  const params = await searchParams;
  const book = params.book ?? "창세기";
  const chapter = Number(params.chapter ?? "1") || 1;

  const verses = getChapterVerses(book, chapter);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">
          {book} {chapter}장
        </h1>
        <BookChapterSelector book={book} chapter={chapter} />
      </div>

      <VerseList verses={verses} />
    </main>
  );
}
