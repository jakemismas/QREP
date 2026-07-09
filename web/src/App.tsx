/*
 * App shell (S2, issue #42). Composes the providers, renders the always-on
 * header, and switches between the start screen and the editor purely on
 * whether a model is loaded. The editor draws from the parsed model
 * immediately; nothing here waits on the engine.
 *
 * Layout follows MOCK-NOTES: desktop (>=720px) shows the canvas beside a
 * 376px panel with a segmented Tabs control (Fabrics active; Sizing and
 * Pattern are disabled teasers); phone shows one region at a time with a
 * bottom tab bar.
 */
import { useCallback, useEffect, useState } from "react";
import { ThemeProvider, ToastProvider, Tabs } from "./ui";
import type { TabItem } from "./ui";
import { EngineProvider } from "./engine/useEngine";
import { ProjectProvider, useProject } from "./state/project";
import { Header } from "./shell/Header";
import { StartScreen } from "./shell/StartScreen";
import { OpenModal } from "./shell/OpenModal";
import { QuiltCanvas, FabricsPanel } from "./viewer";
import type { QuiltModel, ModelSummary } from "./model/types";

type PhoneTab = "quilt" | "fabrics" | "sizing" | "pattern";

// The shipped Tabs primitive (TabItem: id/label/disabled) has no per-tab
// tooltip slot, so the "coming soon" hint on the disabled tabs is carried by
// their disabled styling rather than a tooltip.
const DESK_TABS: TabItem[] = [
  { id: "fabrics", label: "Fabrics" },
  { id: "sizing", label: "Sizing", disabled: true },
  { id: "pattern", label: "Pattern", disabled: true },
];

const PHONE_TABS: { id: PhoneTab; label: string; icon: string; disabled?: boolean }[] = [
  { id: "quilt", label: "Quilt", icon: "M3.5 3.5h15v15h-15zM3.5 9h15M3.5 14h15M9 3.5v15M14 3.5v15" },
  { id: "fabrics", label: "Fabrics", icon: "M3.5 3.5h9v9h-9zM9.5 9.5h9v9h-9z" },
  { id: "sizing", label: "Sizing", icon: "M2.5 7.5h17v7h-17zM6 7.5v3.5M9.5 7.5v3.5M13 7.5v3.5M16.5 7.5v3.5", disabled: true },
  { id: "pattern", label: "Pattern", icon: "M4.5 3h10l4 4v12h-14zM8 9.5h7M8 13h7M8 16.5h5", disabled: true },
];

function useIsDesktop(): boolean {
  const [isDesk, setIsDesk] = useState(() =>
    typeof window === "undefined" ? true : window.innerWidth >= 720,
  );
  useEffect(() => {
    const query = window.matchMedia("(min-width: 720px)");
    const update = () => setIsDesk(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return isDesk;
}

function DesktopEditor({ model, summary }: { model: QuiltModel; summary: ModelSummary | null }) {
  return (
    <div data-testid="editor" className="editor editor--desk">
      <section className="canvas-area">
        <QuiltCanvas model={model} />
      </section>
      <aside className="side-panel">
        <Tabs tabs={DESK_TABS} active="fabrics" onSelect={() => undefined} />
        <FabricsPanel model={model} summary={summary} />
      </aside>
    </div>
  );
}

function PhoneTabBar({ tab, onTab }: { tab: PhoneTab; onTab: (tab: PhoneTab) => void }) {
  return (
    <nav className="phone-tabbar" data-noprint>
      {PHONE_TABS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`phone-tab${tab === item.id ? " phone-tab--active" : ""}`}
          disabled={item.disabled}
          aria-current={tab === item.id ? "page" : undefined}
          onClick={() => onTab(item.id)}
        >
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            <path d={item.icon} stroke="currentColor" strokeWidth="1.8" />
          </svg>
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function PhoneEditor({
  model,
  summary,
  tab,
  onTab,
}: {
  model: QuiltModel;
  summary: ModelSummary | null;
  tab: PhoneTab;
  onTab: (tab: PhoneTab) => void;
}) {
  return (
    <div data-testid="editor" className="editor editor--phone">
      <div className="phone-region">
        {tab === "quilt" ? <QuiltCanvas model={model} /> : null}
        {tab === "fabrics" ? <FabricsPanel model={model} summary={summary} /> : null}
      </div>
      <PhoneTabBar tab={tab} onTab={onTab} />
    </div>
  );
}

function AppShell() {
  const { model, modelJson, summary } = useProject();
  const isDesk = useIsDesktop();
  const [modalOpen, setModalOpen] = useState(false);
  const [tab, setTab] = useState<PhoneTab>("quilt");
  const openModal = useCallback(() => setModalOpen(true), []);

  // A freshly-opened project starts on the Quilt tab (phone); desktop always
  // shows the canvas, so this only matters below 720px.
  useEffect(() => {
    if (modelJson !== null) setTab("quilt");
  }, [modelJson]);

  return (
    <div className="app-root">
      <Header isDesk={isDesk} onOpenProject={openModal} />
      <main className={model === null ? "app-main" : "app-main app-main--editor"}>
        {model === null ? (
          <StartScreen onOpenProject={openModal} />
        ) : isDesk ? (
          <DesktopEditor model={model} summary={summary} />
        ) : (
          <PhoneEditor model={model} summary={summary} tab={tab} onTab={setTab} />
        )}
      </main>
      <OpenModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <EngineProvider>
          <ProjectProvider>
            <AppShell />
          </ProjectProvider>
        </EngineProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
