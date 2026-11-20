import { shortCodec } from "./codecs.ts";
import type { JobOut } from "./queue.ts";

export type Chip = "all" | "downloading" | "video" | "audio";

export function libraryItems(done: JobOut[], allActive: JobOut[], chip: Chip): JobOut[] {
  // The queue poll can lag the library load, so a just-finished job may be in both.
  const doneIds = new Set(done.map((j) => j.id));
  const active = allActive.filter((j) => !doneIds.has(j.id));
  switch (chip) {
    case "all":
      return [...active, ...done];
    case "downloading":
      return active;
    default:
      return [...active, ...done].filter((j) => j.media_kind === chip);
  }
}

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
