const URL_RE = /https?:\/\/\S+/;

// The first http(s) URL in the share, text or title params. `text` may hold words around it.
export function sharedUrl(search: string): string | null {
  const params = new URLSearchParams(search);
  for (const key of ["share", "text", "title"]) {
    const match = params.get(key)?.match(URL_RE);
    if (match) return match[0];
  }
  return null;
}
