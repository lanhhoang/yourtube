import { applyTheme, currentTheme, type ThemeChoice } from "./theme.ts";

// Shared by the rail tile and the Settings control so they always agree.
export const themeState = $state({ choice: currentTheme() });

export function setTheme(choice: ThemeChoice): void {
  themeState.choice = choice;
  applyTheme(choice);
}
