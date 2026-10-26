import type { ReactNode } from "react";

export function MonthPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="month"
      className="month-picker"
      value={value}
      onChange={(e) => e.target.value && onChange(e.target.value)}
      aria-label="Mes"
    />
  );
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="error">{error instanceof Error ? error.message : String(error)}</p>;
}

export function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card tile">
      <span className="muted small">{label}</span>
      <strong className="tile-value">{value}</strong>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card muted">{children}</div>;
}

export function confirmDelete(what: string): boolean {
  return window.confirm(`¿Eliminar ${what}? Esta acción no se puede deshacer.`);
}

export function Progress({ pct }: { pct: string | null }) {
  const width = Math.max(0, Math.min(Number(pct ?? 0), 100));
  return (
    <div className="progress" title={pct ? `${Number(pct).toFixed(1)} %` : undefined}>
      <div style={{ width: `${width}%` }} />
    </div>
  );
}
