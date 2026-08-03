import type { SearchResult } from "@/types/search";

interface SearchResultItemProps {
  result: SearchResult;
}

function renderHighlightedText(text: string, highlight?: [number, number][]) {
  if (!highlight || highlight.length === 0) return text;

  const nodes: React.ReactNode[] = [];
  let cursor = 0;

  highlight.forEach(([start, end], index) => {
    if (start > cursor) nodes.push(text.slice(cursor, start));
    nodes.push(
      <mark
        key={index}
        className="rounded bg-yellow-200 px-0.5 dark:bg-yellow-500/40"
      >
        {text.slice(start, end)}
      </mark>
    );
    cursor = end;
  });

  if (cursor < text.length) nodes.push(text.slice(cursor));

  return nodes;
}

export default function SearchResultItem({ result }: SearchResultItemProps) {
  return (
    <li className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
        {result.book} {result.chapter}장 {result.verse}절
      </p>
      <p className="mt-1 leading-relaxed text-zinc-900 dark:text-zinc-50">
        {renderHighlightedText(result.text, result.highlight)}
      </p>
    </li>
  );
}
