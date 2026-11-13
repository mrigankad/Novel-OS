/** Tiny word-level diff (LCS over tokens). No dependency; fine for chapter-sized texts. */

export type DiffPart = { type: "same" | "add" | "del"; text: string };

const tokenize = (s: string): string[] => [...(s.match(/\s+|[^\s]+/g) ?? [])];

export function wordDiff(before: string, after: string): DiffPart[] {
  let a = tokenize(before);
  let b = tokenize(after);

  // Trim the shared head and tail so the quadratic table stays small.
  let head = 0;
  while (head < a.length && head < b.length && a[head] === b[head]) head++;
  let tail = 0;
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++;
  const prefix = a.slice(0, head).join("");
  const suffix = tail ? a.slice(a.length - tail).join("") : "";
  a = a.slice(head, a.length - tail);
  b = b.slice(head, b.length - tail);

  const parts: DiffPart[] = [];
  const push = (type: DiffPart["type"], text: string) => {
    if (!text) return;
    const last = parts[parts.length - 1];
    if (last && last.type === type) last.text += text;
    else parts.push({ type, text });
  };
  push("same", prefix);

  if (a.length * b.length > 4_000_000) {
    // Too big to align: show it as a replacement.
    push("del", a.join(""));
    push("add", b.join(""));
  } else {
    const m = a.length, n = b.length;
    const dp = Array.from({ length: m + 1 }, () => new Uint32Array(n + 1));
    for (let i = m - 1; i >= 0; i--) {
      for (let j = n - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (a[i] === b[j]) { push("same", a[i]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { push("del", a[i]); i++; }
      else { push("add", b[j]); j++; }
    }
    while (i < m) push("del", a[i++]);
    while (j < n) push("add", b[j++]);
  }
  push("same", suffix);
  return parts;
}

export function diffStats(parts: DiffPart[]) {
  const count = (t: string) => (t.match(/[^\s]+/g) ?? []).length;
  return {
    added: parts.filter((p) => p.type === "add").reduce((s, p) => s + count(p.text), 0),
    removed: parts.filter((p) => p.type === "del").reduce((s, p) => s + count(p.text), 0),
  };
}
