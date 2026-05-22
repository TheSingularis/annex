import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { Theme, ThemeTokens, themes, getSavedTheme, saveTheme } from "./theme";

interface ThemeContextValue {
  theme: Theme;
  tokens: ThemeTokens;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getSavedTheme);

  useEffect(() => {
    document.body.style.background = themes[theme].bg;
  }, [theme]);

  const toggle = () => {
    setTheme(t => {
      const next = t === "light" ? "dark" : "light";
      saveTheme(next);
      return next;
    });
  };

  return (
    <ThemeContext.Provider value={{ theme, tokens: themes[theme], toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
