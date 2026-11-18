import type { components } from "./api.gen.ts";

export type QualityCap = components["schemas"]["QualityCap"];

export const CAP_OPTIONS: { value: QualityCap; label: string }[] = [
  { value: "best", label: "Best available" },
  { value: "2160", label: "Up to 2160p" },
  { value: "1440", label: "Up to 1440p" },
  { value: "1080", label: "Up to 1080p" },
  { value: "720", label: "Up to 720p" },
  { value: "480", label: "Up to 480p" },
  { value: "audio", label: "Audio only" },
];

export const DEFAULT_CAP: QualityCap = "1080";

// Same rule as the server: a numeric cap and a best short side under it.
export function isBelowCap(cap: QualityCap, best: number | null): boolean {
  return /^\d+$/.test(cap) && best !== null && best < Number(cap);
}

type Row = components["schemas"]["StreamRow"];

export function isHdr(row: Row): boolean {
  return row.dynamic_range !== null && row.dynamic_range !== "SDR";
}

function sideOf(row: Row): number | null {
  const sides = [row.width, row.height].filter((v): v is number => !!v);
  return sides.length ? Math.min(...sides) : null;
}

function sides(rows: Row[]): number[] {
  return rows.map(sideOf).filter((s): s is number => s !== null);
}

export function hdrSide(rows: Row[]): number | null {
  const s = sides(rows.filter(isHdr));
  return s.length ? Math.max(...s) : null;
}

// The short side the server's `res[:N]` sort picks: the largest <= N, else the smallest above N.
export function cappedSide(cap: QualityCap, rows: Row[]): number | null {
  const all = sides(rows);
  if (cap === "audio" || all.length === 0) return null;
  if (cap === "best") return Math.max(...all);
  const n = Number(cap);
  const under = all.filter((s) => s <= n);
  return under.length ? Math.max(...under) : Math.min(...all);
}

export type HdrAtCap = { kind: "none" } | { kind: "yes" } | { kind: "below"; side: number };

export function hdrAtCap(cap: QualityCap, rows: Row[]): HdrAtCap {
  const top = hdrSide(rows);
  const capped = cappedSide(cap, rows);
  if (top === null || capped === null) return { kind: "none" };
  if (sides(rows.filter(isHdr)).includes(capped)) return { kind: "yes" };
  if (top < capped) return { kind: "below", side: top };
  return { kind: "none" };
}
