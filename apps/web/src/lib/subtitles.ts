/** Menu label for a subtitle language: "French", or "French (auto)" for `fr-orig`. */
export function trackLabel(lang: string, locale?: string): string {
  const base = lang.replace(/-orig$/, "");
  try {
    const name =
      new Intl.DisplayNames([locale ?? navigator.language], { type: "language" }).of(base) ?? base;
    return lang.endsWith("-orig") ? `${name} (auto)` : name;
  } catch {
    return lang;
  }
}
