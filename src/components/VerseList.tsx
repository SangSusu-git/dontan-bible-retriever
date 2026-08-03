import type { BibleVerse } from "@/types/bible";

interface VerseListProps {
  verses: BibleVerse[];
}

export default function VerseList({ verses }: VerseListProps) {
  if (verses.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        아직 이 장의 샘플 데이터가 없습니다. (현재는 창세기 1장만 준비되어 있습니다)
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {verses.map((verse) => (
        <li key={verse.verse} className="flex gap-3 leading-relaxed">
          <span className="mt-0.5 shrink-0 text-sm font-semibold text-zinc-400 dark:text-zinc-500">
            {verse.verse}
          </span>
          <span className="text-zinc-900 dark:text-zinc-50">{verse.text}</span>
        </li>
      ))}
    </ol>
  );
}
