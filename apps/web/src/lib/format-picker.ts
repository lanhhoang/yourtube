import type { components } from "./api.gen.ts";

export type StreamPicker = components["schemas"]["StreamPicker"];
export type Selection = { videoId: string | null; audioId: string | null };

// Picking the selected id again clears it.
export function toggle(sel: Selection, kind: "video" | "audio", id: string): Selection {
  if (kind === "video") return { ...sel, videoId: sel.videoId === id ? null : id };
  return { ...sel, audioId: sel.audioId === id ? null : id };
}

export function expectedContainer(picker: StreamPicker, sel: Selection): string {
  return (
    picker.expected_container_by_pair[`${sel.videoId ?? ""}|${sel.audioId ?? ""}`] ?? "unknown"
  );
}

export function hasExact(sel: Selection): boolean {
  return sel.videoId !== null || sel.audioId !== null;
}
