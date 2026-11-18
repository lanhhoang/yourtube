import type { components } from "./api.gen.ts";
import type { CheckResult } from "./checker.ts";
import type { Selection } from "./format-picker.ts";
import type { QualityCap } from "./quality.ts";

export type SourceEntry = components["schemas"]["SourceEntry"];
export type SourcesResult = components["schemas"]["SourcesResult"];
export type JobCreate = components["schemas"]["JobCreate"];

export type Override = {
  selection: Selection;
  subtitles: boolean;
  outputTemplate: string;
  audioBitrate: string;
};
export type Check = "idle" | "checking" | CheckResult;
export type EntryState = {
  entry: SourceEntry;
  selected: boolean;
  check: Check;
  override: Override | null;
};
export type Header = {
  cap: QualityCap;
  subtitles: boolean;
  outputTemplate: string;
  audioBitrate: string;
};

export function initialEntries(result: SourcesResult): EntryState[] {
  return result.entries.map((entry): EntryState => {
    if (entry.error_code) {
      return {
        entry,
        selected: false,
        check: { ok: false, message: entry.error_message ?? "Unavailable" },
        override: null,
      };
    }
    if (entry.details) {
      return { entry, selected: true, check: { ok: true, details: entry.details }, override: null };
    }
    return { entry, selected: true, check: "checking", override: null };
  });
}

export function isUnavailable(e: EntryState): boolean {
  return typeof e.check === "object" && !e.check.ok;
}

function withSelected(e: EntryState, selected: boolean): EntryState {
  if (isUnavailable(e)) return e;
  if (selected) return { ...e, selected: true, check: e.check === "idle" ? "checking" : e.check };
  return { ...e, selected: false, check: e.check === "checking" ? "idle" : e.check };
}

export function setSelected(entries: EntryState[], index: number, selected: boolean): EntryState[] {
  return entries.map((e, i) => (i === index ? withSelected(e, selected) : e));
}

export function selectAll(entries: EntryState[], selected: boolean): EntryState[] {
  return entries.map((e) => withSelected(e, selected));
}

export function applyResult(entries: EntryState[], index: number, r: CheckResult): EntryState[] {
  return entries.map((e, i) =>
    i !== index ? e : { ...e, check: r, selected: r.ok ? e.selected : false },
  );
}

export function setOverride(
  entries: EntryState[],
  index: number,
  override: Override | null,
): EntryState[] {
  return entries.map((e, i) => (i === index ? { ...e, override } : e));
}

export type AddState =
  | { kind: "empty" }
  | { kind: "checking"; done: number; total: number }
  | { kind: "ready"; count: number };

export function addState(entries: EntryState[]): AddState {
  const selected = entries.filter((e) => e.selected);
  if (selected.length === 0) return { kind: "empty" };
  const done = selected.filter((e) => typeof e.check === "object" && e.check.ok).length;
  return done < selected.length
    ? { kind: "checking", done, total: selected.length }
    : { kind: "ready", count: selected.length };
}

const blank = (s: string): string | null => s.trim() || null;

export function buildJobs(entries: EntryState[], header: Header): JobCreate[] {
  const jobs: JobCreate[] = [];
  for (const e of entries) {
    if (!e.selected || typeof e.check !== "object" || !e.check.ok) continue;
    const d = e.check.details;
    const o = e.override;
    jobs.push({
      url: d.url,
      title: d.title ?? e.entry.title,
      uploader: d.uploader ?? e.entry.uploader,
      duration: d.duration ?? e.entry.duration,
      thumbnail: d.thumbnail ?? e.entry.thumbnail,
      quality_cap: header.cap,
      video_format_id: o?.selection.videoId ?? null,
      audio_format_id: o?.selection.audioId ?? null,
      subtitles: o ? o.subtitles : header.subtitles,
      output_template: blank(o ? o.outputTemplate : header.outputTemplate),
      audio_bitrate: blank(o ? o.audioBitrate : header.audioBitrate),
    });
  }
  return jobs;
}
