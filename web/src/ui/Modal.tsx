/**
 * Modal (S2). Warm 60% backdrop, radius-18 panel, close button, Escape and
 * backdrop-click both close. The panel is a sibling of the backdrop, so
 * clicks inside the panel never reach the backdrop.
 */
import { useEffect } from "react";
import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="q-modal" data-noprint>
      <div className="q-modal__backdrop" onClick={onClose} />
      <div className="q-modal__panel" role="dialog" aria-modal="true" aria-label={title}>
        <div className="q-modal__head">
          <h2 className="q-modal__title">{title}</h2>
          <button
            type="button"
            className="q-modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <div className="q-modal__body">{children}</div>
      </div>
    </div>
  );
}
