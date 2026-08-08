/** Curated genre chips for New Manuscript - keep the list short and hybrid-friendly. */
export const GENRE_OPTIONS = [
  "Fantasy",
  "Romance",
  "Thriller",
  "Mystery",
  "Sci-Fi",
  "Literary",
  "Horror",
  "Historical",
  "YA",
  "Adult",
  "Dark",
  "Humor",
  "Adventure",
  "Contemporary",
] as const;

/** Merge chip selections + Other into the genres array sent to the API. */
export function mergeGenres(selected: string[], other: string): string[] {
  const out = [...selected];
  const t = other.trim();
  if (t && !out.some((s) => s.toLowerCase() === t.toLowerCase())) out.push(t);
  return out;
}
