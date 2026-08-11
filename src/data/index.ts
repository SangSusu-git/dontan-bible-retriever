import type { BibleVerse } from "@/types/bible";
import bibleKo from "./bible.ko.json";

export const bibleVerses: BibleVerse[] = bibleKo as BibleVerse[];

export function getChapterVerses(book: string, chapter: number): BibleVerse[] {
  return bibleVerses
    .filter((verse) => verse.book === book && verse.chapter === chapter)
    .sort((a, b) => a.verse - b.verse);
}
