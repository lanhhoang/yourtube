import { CAP_OPTIONS, hdrAtCap, isBelowCap, type QualityCap } from "./quality.ts";
import type { EntryState } from "./playlist.ts";

export type Badge =
  | { kind: "below"; label: string }
  | { kind: "custom"; label: string }
  | { kind: "unavailable"; label: "Unavailable"; message: string };

export function badgeFor(e: EntryState, cap: QualityCap): Badge | null {
  const check = e.check;
  if (typeof check === "object" && !check.ok) {
    return { kind: "unavailable", label: "Unavailable", message: check.message };
  }
  const ok = typeof check === "object" ? check : null;
  if (e.override) {
    const { videoId, audioId } = e.override.selection;
    if (videoId !== null) {
      const row = ok?.details.picker.video_streams.find((r) => r.format_id === videoId);
      const side = row
        ? row.width !== null && row.height !== null
          ? Math.min(row.width, row.height)
          : row.height
        : null;
      if (side !== null && side !== undefined)
        return { kind: "custom", label: `${side}p · custom` };
    } else if (audioId !== null) {
      return { kind: "custom", label: "audio · custom" };
    }
    const label = CAP_OPTIONS.find((o) => o.value === cap)?.label ?? cap;
    return { kind: "custom", label: `${label} · custom` };
  }
  const best = ok?.details.best_short_side ?? null;
  if (ok && best !== null && isBelowCap(cap, best)) return { kind: "below", label: `${best}p max` };
  return null;
}

export function hdrBadgeFor(e: EntryState, cap: QualityCap): { label: string } | null {
  if (e.override || typeof e.check !== "object" || !e.check.ok) return null;
  const at = hdrAtCap(cap, e.check.details.picker.video_streams);
  if (at.kind === "yes") return { label: "HDR" };
  if (at.kind === "below") return { label: `HDR ≤${at.side}p` };
  return null;
}
