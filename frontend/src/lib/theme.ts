export type Theme = "light" | "dark";

export interface ThemeTokens {
  bg: string;
  surface: string;
  surfaceHover: string;
  border: string;
  text: string;
  textMuted: string;
  navBg: string;
  navActive: string;
  navText: string;
  navTextActive: string;
  inputBorder: string;
  shadow: string;
  warningBg: string;
  warningText: string;
}

export const themes: Record<Theme, ThemeTokens> = {
  light: {
    bg: "#f8f9fa",
    surface: "#ffffff",
    surfaceHover: "#f1f3f5",
    border: "#dee2e6",
    text: "#212529",
    textMuted: "#6c757d",
    navBg: "#1a1a2e",
    navActive: "#16213e",
    navText: "#aaa",
    navTextActive: "#fff",
    inputBorder: "#dee2e6",
    shadow: "0 1px 3px rgba(0,0,0,.1)",
    warningBg: "#fff3cd",
    warningText: "#6c757d",
  },
  dark: {
    bg: "#0f0f17",
    surface: "#1a1a2e",
    surfaceHover: "#16213e",
    border: "#2d2d44",
    text: "#e2e2ef",
    textMuted: "#8888aa",
    navBg: "#111120",
    navActive: "#0f0f17",
    navText: "#8888aa",
    navTextActive: "#e2e2ef",
    inputBorder: "#2d2d44",
    shadow: "0 1px 3px rgba(0,0,0,.4)",
    warningBg: "#2a2410",
    warningText: "#aaa37a",
  },
};

const STORAGE_KEY = "annex-theme";

export function getSavedTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function saveTheme(theme: Theme) {
  localStorage.setItem(STORAGE_KEY, theme);
}
