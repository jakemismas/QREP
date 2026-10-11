/*
 * Lightbox: the reusable Photo / Side by side / Quilt viewer, opened from
 * the results screen and from the editor's "Compare with your photo". Its
 * stylesheet ships with it, so it overlays the viewport wherever it mounts
 * (web-03).
 */
import { useEffect } from "react";
import { QuiltCanvas } from "../../viewer";
import type { QuiltModel } from "../../model/types";
import "./shared.css";
import "./Lightbox.css";

export type LbTab = "photo" | "side" | "quilt";

export function Lightbox({
  photoUrl,
  model,
  tab,
  onTab,
  onClose,
  showUncertain = false,
}: {
  photoUrl: string | null;
  model: QuiltModel | null;
  tab: LbTab;
  onTab: (tab: LbTab) => void;
  onClose: () => void;
  showUncertain?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const tabs: { id: LbTab; label: string }[] = [
    { id: "photo", label: "Photo" },
    { id: "side", label: "Side by side" },
    { id: "quilt", label: "Quilt" },
  ];

  const photoEl = photoUrl ? (
    <img className="pf-lb-photo" src={photoUrl} alt="Your uploaded quilt" />
  ) : (
    <div className="pf-lb-photo pf-photo--gone">Photo cleared</div>
  );
  const quiltEl = model ? (
    <div className="pf-lb-quilt">
      <QuiltCanvas model={model} showUncertain={showUncertain} />
    </div>
  ) : null;

  return (
    <div className="pf-lb" data-testid="lightbox" data-noprint>
      <div className="pf-lb-scrim" onClick={onClose} />
      <div className="pf-lb-inner">
        <div className="pf-lb-bar">
          <span className="pf-lb-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className="pf-lb-tab"
                data-active={t.id === tab || undefined}
                data-testid={`lightbox-tab-${t.id}`}
                onClick={() => onTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </span>
          <button type="button" className="pf-lb-close" aria-label="Close" onClick={onClose}>
            &#10005;
          </button>
        </div>
        <div className="pf-lb-stage">
          {tab === "photo" ? photoEl : null}
          {tab === "quilt" ? quiltEl : null}
          {tab === "side" ? (
            <div className="pf-lb-side">
              {photoEl}
              {quiltEl}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
