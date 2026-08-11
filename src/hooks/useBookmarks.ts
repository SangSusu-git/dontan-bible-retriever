"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Bookmark } from "@/types/bookmark";

const STORAGE_KEY = "bible-app:bookmarks";
const listeners = new Set<() => void>();
const EMPTY_BOOKMARKS: Bookmark[] = [];

let cachedBookmarks: Bookmark[] | null = null;

/**
 * useSyncExternalStore의 getSnapshot은 데이터가 안 바뀌었으면 항상 같은
 * 참조를 반환해야 한다. 매번 새 배열을 만들면 React가 스냅샷이 계속
 * 바뀐 것으로 보고 무한 렌더링에 빠진다(Minified React error #185).
 */
function readStoredBookmarks(): Bookmark[] {
  if (cachedBookmarks) return cachedBookmarks;
  if (typeof window === "undefined") return EMPTY_BOOKMARKS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    cachedBookmarks = raw ? (JSON.parse(raw) as Bookmark[]) : EMPTY_BOOKMARKS;
  } catch {
    cachedBookmarks = EMPTY_BOOKMARKS;
  }
  return cachedBookmarks;
}

function writeStoredBookmarks(bookmarks: Bookmark[]) {
  cachedBookmarks = bookmarks;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getServerSnapshot(): Bookmark[] {
  return EMPTY_BOOKMARKS;
}

export function bookmarkId(verse: Pick<Bookmark, "book" | "chapter" | "verse" | "translation">) {
  return `${verse.book}-${verse.chapter}-${verse.verse}-${verse.translation}`;
}

export function useBookmarks() {
  const bookmarks = useSyncExternalStore(subscribe, readStoredBookmarks, getServerSnapshot);

  const addBookmark = useCallback((verse: Omit<Bookmark, "id" | "createdAt">) => {
    const bookmark: Bookmark = {
      ...verse,
      id: bookmarkId(verse),
      createdAt: new Date().toISOString(),
    };
    const next = [bookmark, ...readStoredBookmarks().filter((b) => b.id !== bookmark.id)];
    writeStoredBookmarks(next);
  }, []);

  const removeBookmark = useCallback((id: string) => {
    const next = readStoredBookmarks().filter((b) => b.id !== id);
    writeStoredBookmarks(next);
  }, []);

  const isBookmarked = useCallback(
    (id: string) => bookmarks.some((b) => b.id === id),
    [bookmarks]
  );

  return { bookmarks, addBookmark, removeBookmark, isBookmarked };
}
