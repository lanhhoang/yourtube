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
