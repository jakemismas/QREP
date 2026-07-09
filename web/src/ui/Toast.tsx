/**
 * Toast system (S2). Single slot, bottom-center, never stacks: a new push
 * replaces the current toast and resets the auto-dismiss timer. Colors are
 * fixed in both themes (tokens.css). The visible element carries
 * data-testid="toast".
 */
import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";

export type ToastTone = "success" | "error";

interface ToastApi {
  push: (message: string, tone?: ToastTone) => void;
}

interface ToastState {
  message: string;
  tone: ToastTone;
  id: number;
}

const ToastContext = createContext<ToastApi | null>(null);

// Main-mock behavior: replace-and-reset with a ~3.6s auto-dismiss.
const DISMISS_MS = 3600;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0);

  const push = useCallback((message: string, tone: ToastTone = "success") => {
    if (timer.current !== null) clearTimeout(timer.current);
    const id = ++seq.current;
    setToast({ message, tone, id });
    timer.current = setTimeout(() => {
      // Only clear if this is still the toast we scheduled.
      setToast((current) => (current !== null && current.id === id ? null : current));
      timer.current = null;
    }, DISMISS_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      {toast !== null && (
        // key={id} remounts the node so the qToast entry animation replays
        // when one toast replaces another.
        <div
          key={toast.id}
          className="q-toast"
          data-testid="toast"
          data-tone={toast.tone}
          data-noprint
          role="status"
          aria-live="polite"
        >
          <span className="q-toast__glyph" aria-hidden="true">
            {toast.tone === "success" ? "✓" : "⚠"}
          </span>
          <span>{toast.message}</span>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (api === null) throw new Error("useToast requires ToastProvider");
  return api;
}
