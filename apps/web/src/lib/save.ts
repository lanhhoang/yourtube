export const SHARE_LIMIT_BYTES = 500 * 1024 * 1024;
const FOLD_BYTES = 16 * 1024 * 1024;

export function saveMode(size: number | null, canShare: boolean): "share" | "link" {
  return canShare && size !== null && size >= 1 && size <= SHARE_LIMIT_BYTES ? "share" : "link";
}

export function canShareFiles(): boolean {
  try {
    return (
      typeof navigator.canShare === "function" &&
      navigator.canShare({ files: [new File([], "x.mp4", { type: "video/mp4" })] })
    );
  } catch {
    return false;
  }
}

// Strips characters that file systems and share targets reject.
export function fileName(title: string | null, format: string | null): string {
  // biome-ignore lint/suspicious/noControlCharactersInRegex: control characters are the point
  const base = (title ?? "").replace(/[/\\:*?"<>|\x00-\x1f]+/g, "-").trim() || "download";
  return format ? `${base}.${format}` : base;
}

export async function fetchBlob(
  url: string,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<Blob> {
  const res = await fetch(url, { signal });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const total = Number(res.headers.get("Content-Length")) || 0;
  const reader = res.body.getReader();
  // Fold chunks into the Blob as they arrive: WebKit keeps Blob data off the JS heap, so a
  // large file never sits in memory twice.
  let acc = new Blob([]);
  let chunks: Uint8Array<ArrayBuffer>[] = [];
  let pending = 0;
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value as Uint8Array<ArrayBuffer>);
    received += value.length;
    pending += value.length;
    if (pending >= FOLD_BYTES) {
      acc = new Blob([acc, ...chunks]);
      chunks = [];
      pending = 0;
    }
    if (total) onProgress(Math.min(1, received / total));
  }
  return new Blob([acc, ...chunks], { type: res.headers.get("Content-Type") ?? "" });
}
