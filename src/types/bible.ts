export interface BibleVerse {
  book: string;
  chapter: number;
  verse: number;
  translation: string;
  text: string;
}

export interface BookInfo {
  name: string;
  testament: "구약" | "신약";
  chapterCount: number;
}
