export type FetchOptions = { useProxy: boolean; useCookies: boolean };

export const FETCH_OPTIONS_KEY = "yt-fetch-options";

export function readFetchOptions(stored: string | null): FetchOptions {
  const off = { useProxy: false, useCookies: false };
  if (stored === null) return off;
  try {
    const parsed = JSON.parse(stored);
    return {
      useProxy: parsed?.useProxy === true,
      useCookies: parsed?.useCookies === true,
    };
  } catch {
    return off;
  }
}

export function saveFetchOptions(o: FetchOptions): void {
  localStorage.setItem(FETCH_OPTIONS_KEY, JSON.stringify(o));
}
