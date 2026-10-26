import { useState } from "react";
import { usePlan, useScenario } from "../api/hooks";
import { useMe } from "../auth/useAuth";
import { RuleBars } from "../components/RuleBars";
import { Empty, ErrorText, Tile } from "../components/ui";
import { currentMonth, fmtMoney } from "../lib/format";

export default function ScenariosPage() {
  const { data: user } = useMe();
  const base = user?.base_currency ?? "USD";
  const month = `${currentMonth()}-01`;
  const { data: plan, isLoading } = usePlan(month);
  const [target, setTarget] = useState<number | null>(null);
  const m = (v: string | null | undefined) => fmtMoney(v, base);

  if (isLoading || !plan) return <p className="muted">Cargando…</p>;

  const lifestyle = Number(plan.fixed_lifestyle) + Number(plan.variable_lifestyle);
  const income = Number(plan.income_avg);
  const max = Math.max(Math.ceil(Math.max(lifestyle * 2, income) / 10) * 10, 100);
  const value = target ?? Math.round(lifestyle / 10) * 10;
  const { data: s, error } = useScenario(month, value.toFixed(2));
  const enough = s && s.fund_months !== null;

  if (income === 0)
    return (
      <>
        <header className="page-header">
          <h1>Escenarios</h1>
        </header>
        <Empty>Registra ingresos de los últimos 3 meses para poder simular.</Empty>
      </>
    );

  return (
    <>
      <header className="page-header">
        <h1>Escenarios</h1>
        <span className="muted">Ingreso promedio: {m(plan.income_avg)}</span>
      </header>

      <div className="card form">
        <h2>¿Cuánto quieres gastar al mes en vivir bien?</h2>
        <p className="muted small">
          Hoy vives con {m(String(lifestyle + Number(plan.survive)))} al mes ({m(plan.survive)} para sobrevivir +{" "}
          {m(String(lifestyle))} de estilo de vida). Mueve el control o escribe un monto.
        </p>
        <input
          className="slider"
          type="range"
          min={0}
          max={max}
          step={10}
          value={value}
          onChange={(e) => setTarget(Number(e.target.value))}
          aria-label="Gasto de estilo de vida al mes"
        />
        <div className="row gap-sm">
          <input
            type="number"
            min={0}
            step="any"
            value={value}
            onChange={(e) => setTarget(Math.max(Number(e.target.value) || 0, 0))}
            aria-label="Monto exacto"
          />
          <span className="muted small">{base} al mes de estilo de vida</span>
        </div>
      </div>
      <ErrorText error={error} />

      {s && (
        <>
          <section className="tiles">
            <Tile label="Costo total de vivir bien" value={m(s.live_target)} hint={`sobrevivir ${m(s.survive)} + estilo ${m(s.lifestyle_target)}`} />
            <Tile
              label="Puedes ahorrar al mes"
              value={<span className={Number(s.savings_capacity) < 0 ? "negative" : ""}>{m(s.savings_capacity)}</span>}
            />
            <Tile
              label="Fondo de emergencia"
              value={
                s.fund_months === null
                  ? "No alcanza"
                  : Number(s.fund_months) === 0
                    ? "Ya lo tienes"
                    : `${Number(s.fund_months).toFixed(1)} meses`
              }
              hint={enough ? "para completarlo con ese ahorro" : "con ese gasto no se ahorra nada"}
            />
            <Tile
              label="Ingreso necesario"
              value={m(s.required_income)}
              hint={`tienes ${m(s.income_avg)} de promedio`}
            />
            <Tile
              label="Meta de gasto sostenible"
              value={m(s.max_lifestyle)}
              hint="estilo de vida que cabe con tu ritmo de ahorro actual"
            />
          </section>
          {Number(s.required_income) > Number(s.income_avg) && (
            <p className="warning">
              Para vivir así y mantener tu ahorro necesitas ganar {m(String(Number(s.required_income) - Number(s.income_avg)))}{" "}
              más al mes, en bruto.
            </p>
          )}
        </>
      )}

      <RuleBars plan={plan} />
    </>
  );
}
