export function findHighlightRanges(text: string, query: string): [number, number][] {
  if (!query) return [];

  const ranges: [number, number][] = [];
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();

  let fromIndex = 0;
  while (fromIndex <= lowerText.length) {
    const index = lowerText.indexOf(lowerQuery, fromIndex);
    if (index === -1) break;
    ranges.push([index, index + query.length]);
    fromIndex = index + query.length;
  }

  return ranges;
}
