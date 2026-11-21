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
