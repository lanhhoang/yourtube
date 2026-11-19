export const SHARE_LIMIT_BYTES = 500 * 1024 * 1024;

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
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value as Uint8Array<ArrayBuffer>);
    received += value.length;
    if (total) onProgress(Math.min(1, received / total));
  }
  return new Blob(chunks, { type: res.headers.get("Content-Type") ?? "" });
}
