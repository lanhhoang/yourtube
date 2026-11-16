export type ThemeChoice = "dark" | "light" | "system";

export const THEME_KEY = "theme";

export function readTheme(stored: string | null): ThemeChoice {
  return stored === "light" || stored === "system" ? stored : "dark";
}

export function isDark(choice: ThemeChoice, prefersDark: boolean): boolean {
  return choice === "dark" || (choice === "system" && prefersDark);
}

const darkQuery = () => matchMedia("(prefers-color-scheme: dark)");

export function currentTheme(): ThemeChoice {
  return readTheme(localStorage.getItem(THEME_KEY));
}

function toggle(choice: ThemeChoice): void {
  document.documentElement.classList.toggle("dark", isDark(choice, darkQuery().matches));
}

export function applyTheme(choice: ThemeChoice): void {
  localStorage.setItem(THEME_KEY, choice);
  toggle(choice);
}

export function watchSystemTheme(): () => void {
  const query = darkQuery();
  const onChange = () => toggle(currentTheme());
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
