import { useSchedulePreview } from "../api/hooks";

type Preset = { id: string; label: string; rule: (n: number) => string; needsN?: string };

const PRESETS: Preset[] = [
  { id: "monthly", label: "Mensual", rule: () => "FREQ=MONTHLY" },
  { id: "months", label: "Cada N meses", rule: (n) => `FREQ=MONTHLY;INTERVAL=${n}`, needsN: "meses" },
  { id: "q15last", label: "Quincenal (15 y último día)", rule: () => "FREQ=MONTHLY;BYMONTHDAY=15,-1" },
  { id: "q1_15", label: "Quincenal (1 y 15)", rule: () => "FREQ=MONTHLY;BYMONTHDAY=1,15" },
  { id: "days", label: "Cada N días", rule: (n) => `FREQ=DAILY;INTERVAL=${n}`, needsN: "días" },
  { id: "weeks", label: "Cada N semanas", rule: (n) => `FREQ=WEEKLY;INTERVAL=${n}`, needsN: "semanas" },
  { id: "yearly", label: "Anual", rule: () => "FREQ=YEARLY" },
  { id: "custom", label: "Personalizada (RRULE)", rule: () => "" },
];

const SINGULAR: Record<string, string> = { meses: "Mensual", días: "Diario", semanas: "Semanal" };

function parse(rule: string): { preset: string; n: number } {
  const parts = Object.fromEntries(rule.split(";").map((p) => p.split("=")));
  const n = Number(parts.INTERVAL ?? 1);
  const keys = Object.keys(parts).filter((k) => k !== "FREQ" && k !== "INTERVAL");
  if (keys.length === 0) {
    if (parts.FREQ === "MONTHLY") return { preset: n === 1 ? "monthly" : "months", n };
    if (parts.FREQ === "DAILY") return { preset: "days", n };
    if (parts.FREQ === "WEEKLY") return { preset: "weeks", n };
    if (parts.FREQ === "YEARLY" && n === 1) return { preset: "yearly", n };
  }
  if (rule === "FREQ=MONTHLY;BYMONTHDAY=15,-1") return { preset: "q15last", n: 1 };
  if (rule === "FREQ=MONTHLY;BYMONTHDAY=1,15") return { preset: "q1_15", n: 1 };
  return { preset: "custom", n: 1 };
}

/** Human label for a rule, e.g. "Cada 2 meses". */
export function describeRule(rule: string): string {
  const { preset, n } = parse(rule);
  const p = PRESETS.find((x) => x.id === preset)!;
  if (preset === "custom") return rule;
  if (p.needsN) return n === 1 ? SINGULAR[p.needsN] : `Cada ${n} ${p.needsN}`;
  return p.label;
}

export function FrequencyPicker({ value, onChange }: { value: string; onChange: (rule: string) => void }) {
  const { preset, n } = parse(value);
  const current = PRESETS.find((p) => p.id === preset)!;

  return (
    <div className="grid-2">
      <label>
        Frecuencia
        <select
          value={preset}
          onChange={(e) => {
            const next = PRESETS.find((p) => p.id === e.target.value)!;
            onChange(next.id === "custom" ? value : next.rule(next.needsN ? Math.max(n, 2) : 1));
          }}
        >
          {PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {current.needsN && (
        <label>
          Cada cuántos {current.needsN}
          <input
            type="number"
            min={1}
            max={999}
            value={n}
            onChange={(e) => onChange(current.rule(Math.max(1, Number(e.target.value) || 1)))}
            required
          />
        </label>
      )}
      {preset === "custom" && (
        <label>
          Regla RRULE
          <input
            value={value}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            placeholder="FREQ=MONTHLY;BYMONTHDAY=10,25"
            required
          />
        </label>
      )}
    </div>
  );
}

/** Next dates of a schedule, straight from the backend so it matches what will be generated. */
export function SchedulePreview({ rule, start, end }: { rule: string; start: string; end: string | null }) {
  const { data, error } = useSchedulePreview(rule, start, end);
  if (error) return <p className="error small">{error.message}</p>;
  if (!data) return null;
  return (
    <p className="muted small">
      Próximas fechas: {data.dates.join(" · ") || "ninguna"} · {Number(data.per_month).toLocaleString("es-CO")} veces
      al mes
    </p>
  );
}
