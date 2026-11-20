const CODECS: [string[], string][] = [
  [["avc1", "avc3", "h264"], "h264"],
  [["hev1", "hvc1", "h265", "hevc"], "h265"],
  [["vp09", "vp9"], "vp9"],
  [["vp8"], "vp8"],
  [["av01", "av1"], "av1"],
  [["mp4a", "aac"], "aac"],
  [["opus"], "opus"],
  [["vorbis"], "vorbis"],
  [["ac-3", "ac3"], "ac3"],
  [["ec-3", "eac3"], "eac3"],
  [["flac"], "flac"],
  [["mp3"], "mp3"],
];

export function shortCodec(codec: string | null): string {
  if (!codec) return "";
  const lower = codec.toLowerCase();
  for (const [prefixes, name] of CODECS) {
    if (prefixes.some((p) => lower.startsWith(p))) return name;
  }
  return codec;
}
