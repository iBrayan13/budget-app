import type { Plan } from "../api/types";
import { fmtPct } from "../lib/format";

const RULES = [
  { key: "rule_essential_pct", label: "Esenciales", limit: 50, atLeast: false },
  { key: "rule_lifestyle_pct", label: "Estilo de vida", limit: 30, atLeast: false },
  { key: "rule_savings_pct", label: "Ahorro", limit: 20, atLeast: true },
] as const;

/** Regla 50/30/20 sobre el ingreso promedio. The marker is the target. */
export function RuleBars({ plan }: { plan: Plan }) {
  return (
    <div className="card">
      <h2>Regla 50 / 30 / 20 (sobre tu ingreso promedio)</h2>
      {RULES.map((r) => {
        const value = plan[r.key];
        const pct = value === null ? 0 : Number(value);
        const ok = r.atLeast ? pct >= r.limit : pct <= r.limit;
        return (
          <div key={r.key} className="rule">
            <div className="row-between small">
              <span>{r.label}</span>
              <span>
                {value === null ? "sin ingresos" : fmtPct(value)} · meta {r.atLeast ? "≥" : "≤"} {r.limit}%
              </span>
            </div>
            <div className="bar">
              <div
                className={ok ? "bar-fill ok" : "bar-fill over"}
                style={{ width: `${Math.max(0, Math.min(pct, 100))}%` }}
              />
              <div className="bar-mark" style={{ left: `${r.limit}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
