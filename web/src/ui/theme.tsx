/**
 * Theme provider (S2). Stamps data-skin on <html>, defaults light, persists
 * to localStorage["qrep-skin"]. The design-system tokens key off the
 * data-skin attribute (see tokens.css).
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type Skin = "light" | "dark";

const STORAGE_KEY = "qrep-skin";

interface ThemeValue {
  skin: Skin;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

function readInitialSkin(): Skin {
  try {
    // Only the exact value "dark" flips the default; anything else is light.
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [skin, setSkin] = useState<Skin>(readInitialSkin);

  useEffect(() => {
    document.documentElement.setAttribute("data-skin", skin);
    try {
      localStorage.setItem(STORAGE_KEY, skin);
    } catch {
      // Private-mode / storage-disabled: theme still applies for the session.
    }
  }, [skin]);

  const toggle = useCallback(() => {
    setSkin((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  return <ThemeContext.Provider value={{ skin, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext);
  if (value === null) throw new Error("useTheme requires ThemeProvider");
  return value;
}
