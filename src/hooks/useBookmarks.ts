"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Bookmark } from "@/types/bookmark";

const STORAGE_KEY = "bible-app:bookmarks";
const listeners = new Set<() => void>();

function readStoredBookmarks(): Bookmark[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Bookmark[]) : [];
  } catch {
    return [];
  }
}

function writeStoredBookmarks(bookmarks: Bookmark[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getServerSnapshot(): Bookmark[] {
  return [];
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
