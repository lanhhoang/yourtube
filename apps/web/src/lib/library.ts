import { shortCodec } from "./codecs.ts";
import type { JobOut } from "./queue.ts";

export function qualityLabel(job: JobOut): string {
  if (job.media_kind === "audio") return "Audio";
  return job.resolution_height ? `${job.resolution_height}p` : "";
}

export function formatSize(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

export function watchMeta(job: JobOut): string {
  return [
    job.uploader,
    qualityLabel(job),
    job.media_kind === "video" ? job.dynamic_range : null,
    formatSize(job.file_size),
    shortCodec(job.vcodec),
    shortCodec(job.acodec),
    job.media_format,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function toggle(selected: Set<number>, id: number): Set<number> {
  const next = new Set(selected);
  if (!next.delete(id)) next.add(id);
  return next;
}

export function bulkResultText(deleted: number, failed: number): string {
  if (deleted === 0) return `Couldn't delete ${failed}`;
  return failed ? `Deleted ${deleted}, ${failed} failed` : `Deleted ${deleted}`;
}

export type SortKey = "added-desc" | "added-asc" | "title" | "duration" | "size";
export type KindFilter = "any" | "video" | "audio";
export type LibraryView = {
  sort: SortKey;
  kind: KindFilter;
  channel: string | null;
  playlist: string | null;
};

export const DEFAULT_VIEW: LibraryView = {
  sort: "added-desc",
  kind: "any",
  channel: null,
  playlist: null,
};

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "added-desc", label: "Newest first" },
  { value: "added-asc", label: "Oldest first" },
  { value: "title", label: "Title A–Z" },
  { value: "duration", label: "Longest first" },
  { value: "size", label: "Largest first" },
];

const added = (j: JobOut) => Date.parse(j.finished_at ?? j.created_at);

function byNumberDesc(get: (j: JobOut) => number | null) {
  return (a: JobOut, b: JobOut) => {
    const x = get(a);
    const y = get(b);
    if (x === null || x === undefined) return y === null || y === undefined ? 0 : 1;
    if (y === null || y === undefined) return -1;
    return y - x;
  };
}

export function sortItems(items: JobOut[], sort: SortKey): JobOut[] {
  const cmp: Record<SortKey, (a: JobOut, b: JobOut) => number> = {
    "added-desc": (a, b) => added(b) - added(a),
    "added-asc": (a, b) => added(a) - added(b),
    title: (a, b) => {
      if (a.title === null) return b.title === null ? 0 : 1;
      if (b.title === null) return -1;
      return a.title.localeCompare(b.title, undefined, { sensitivity: "base", numeric: true });
    },
    duration: byNumberDesc((j) => j.duration),
    size: byNumberDesc((j) => j.file_size),
  };
  return [...items].sort(cmp[sort]);
}

export function filterItems(items: JobOut[], view: LibraryView): JobOut[] {
  return items.filter(
    (j) =>
      (view.kind === "any" || j.media_kind === view.kind) &&
      (view.channel === null || j.uploader === view.channel) &&
      (view.playlist === null || j.playlist_title === view.playlist),
  );
}

export type Facet = { value: string; count: number };
export type Facets = { channels: Facet[]; playlists: Facet[] };

function countBy(values: (string | null | undefined)[]): Facet[] {
  const counts = new Map<string, number>();
  for (const v of values) if (v) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => a.value.localeCompare(b.value));
}

export function facets(items: JobOut[]): Facets {
  return {
    channels: countBy(items.map((j) => j.uploader)),
    playlists: countBy(items.map((j) => j.playlist_title)),
  };
}

export function dropStale(view: LibraryView, f: Facets): LibraryView {
  const channel =
    view.channel !== null && f.channels.some((c) => c.value === view.channel) ? view.channel : null;
  const playlist =
    view.playlist !== null && f.playlists.some((p) => p.value === view.playlist)
      ? view.playlist
      : null;
  if (channel === view.channel && playlist === view.playlist) return view;
  return { ...view, channel, playlist };
}

export function activeFilterCount(view: LibraryView): number {
  return (view.kind !== "any" ? 1 : 0) + (view.channel ? 1 : 0) + (view.playlist ? 1 : 0);
}

export function sameFilters(a: LibraryView, b: LibraryView): boolean {
  return a.kind === b.kind && a.channel === b.channel && a.playlist === b.playlist;
}

export const VIEW_KEY = "yt.library.view";

export function readView(raw: string | null): LibraryView {
  if (raw === null) return DEFAULT_VIEW;
  try {
    const p = JSON.parse(raw);
    const str = (v: unknown) => (typeof v === "string" && v !== "" ? v : null);
    return {
      sort: SORT_OPTIONS.some((o) => o.value === p?.sort) ? p.sort : DEFAULT_VIEW.sort,
      kind: p?.kind === "video" || p?.kind === "audio" ? p.kind : "any",
      channel: str(p?.channel),
      playlist: str(p?.playlist),
    };
  } catch {
    return DEFAULT_VIEW;
  }
}

export function saveView(view: LibraryView): void {
  localStorage.setItem(VIEW_KEY, JSON.stringify(view));
}
