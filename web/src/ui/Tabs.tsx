/**
 * Tabs (S2). Segmented-control strip (radius 11 outside / 8 inside) used for
 * the desktop side-panel switcher. Panels are wired by the consumer.
 */

export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onSelect: (id: string) => void;
}

export function Tabs({ tabs, active, onSelect }: TabsProps) {
  return (
    <div className="q-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === active}
          disabled={tab.disabled}
          className="q-tabs__tab"
          data-active={tab.id === active}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
