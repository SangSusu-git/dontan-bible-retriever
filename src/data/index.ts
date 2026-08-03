import type { BibleVerse } from "@/types/bible";
import genesis1Ko from "./genesis1.ko.json";

/**
 * 샘플 성경 본문 전체 목록.
 * 번역본이나 성경책이 추가되면 이 배열에 이어 붙이면 된다.
 */
export const bibleVerses: BibleVerse[] = [...(genesis1Ko as BibleVerse[])];

export function getChapterVerses(book: string, chapter: number): BibleVerse[] {
  return bibleVerses
    .filter((verse) => verse.book === book && verse.chapter === chapter)
    .sort((a, b) => a.verse - b.verse);
}
