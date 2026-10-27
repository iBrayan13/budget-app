import { FormEvent, useState } from "react";
import { useAccounts, useDeleteRoute, useP2PSummary, useRoutes, useSaveRoute } from "../api/hooks";
import type { Account, Route, TransferStepInput } from "../api/types";
import { confirmDelete, Empty, ErrorText, MonthPicker, Tile } from "../components/ui";
import { currentMonth, fmtMoney, fmtPct, monthRange, plain, today } from "../lib/format";

export default function P2PPage() {
  const [month, setMonth] = useState(currentMonth());
  const range = monthRange(month);
  const { data: summary } = useP2PSummary(range);
  const { data: routes, isLoading } = useRoutes(range);
  const { data: accountsData } = useAccounts(true);
  const remove = useDeleteRoute();
  const [editing, setEditing] = useState<Route | null>(null);

  const accounts = accountsData?.accounts ?? [];
  const base = summary?.base_currency ?? accountsData?.base_currency ?? "USD";
  const name = (id: number) => accounts.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <>
      <header className="page-header">
        <h1>P2P y comisiones</h1>
        <MonthPicker value={month} onChange={setMonth} />
      </header>

      <section className="tiles">
        <Tile
          label="Costo total del mes"
          value={fmtMoney(summary?.cost, base)}
          hint={summary ? `${fmtPct(summary.cost_pct)} de lo movido` : undefined}
        />
        <Tile label="Comisiones explícitas" value={fmtMoney(summary?.fees, base)} />
        <Tile label="Spread (tasa P2P vs referencia)" value={fmtMoney(summary?.spread, base)} />
        <Tile
          label="Volumen movido"
          value={fmtMoney(summary?.volume, base)}
          hint={summary ? `${summary.count} transferencias` : undefined}
        />
      </section>
      {summary && summary.missing_rates > 0 && (
        <p className="warning">
          {summary.missing_rates} transferencia(s) sin tasa de referencia no se incluyen. Agrega la tasa en
          Plataformas o en el paso.
        </p>
      )}

      {summary && summary.by_pair.length > 0 && (
        <div className="card table-wrap">
          <h2>Costo por tramo</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Tramo</th>
                <th className="num">Veces</th>
                <th className="num">Volumen</th>
                <th className="num">Costo</th>
                <th className="num">%</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_pair.map((p) => (
                <tr key={`${p.from_account_id}-${p.to_account_id}`}>
                  <td>
                    {name(p.from_account_id)} → {name(p.to_account_id)}
                  </td>
                  <td className="num">{p.count}</td>
                  <td className="num">{fmtMoney(p.volume, base)}</td>
                  <td className="num">{fmtMoney(p.cost, base)}</td>
                  <td className="num">{fmtPct(p.cost_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <RouteForm
        key={editing?.id ?? "new"}
        route={editing}
        accounts={accounts.filter((a) => a.is_active || editing)}
        base={base}
        onDone={() => setEditing(null)}
      />

      <h2>Rutas del mes</h2>
      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : !routes?.length ? (
        <Empty>No hay movimientos P2P en este mes.</Empty>
      ) : (
        <div className="stack">
          {routes.map((r) => (
            <details key={r.id} className="card route">
              <summary>
                <div className="route-head">
                  <div>
                    <strong>{r.name || chainLabel(r, name)}</strong>
                    <div className="muted small">
                      {r.started_on} · {r.name ? chainLabel(r, name) : `${r.steps.length} paso(s)`}
                    </div>
                  </div>
                  <div className="num">
                    <div>
                      {fmtMoney(r.cost.value_out, base)} → {fmtMoney(r.cost.value_in, base)}
                    </div>
                    <div className="cost">
                      Costo {fmtMoney(r.cost.cost, base)} ({fmtPct(r.cost.cost_pct)})
                    </div>
                  </div>
                </div>
              </summary>
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tramo</th>
                    <th className="num">Envié</th>
                    <th className="num">Recibí</th>
                    <th className="num">Comisión</th>
                    <th className="num">Costo</th>
                  </tr>
                </thead>
                <tbody>
                  {r.steps.map((s) => (
                    <tr key={s.id}>
                      <td>{s.step}</td>
                      <td>
                        {name(s.from_account_id)} → {name(s.to_account_id)}
                        <div className="muted small">{s.occurred_on}</div>
                      </td>
                      <td className="num">{fmtMoney(s.amount_out, s.from_currency)}</td>
                      <td className="num">{fmtMoney(s.amount_in, s.to_currency)}</td>
                      <td className="num">{fmtMoney(s.fee_amount, s.fee_currency)}</td>
                      <td className="num">
                        {fmtMoney(s.cost.cost, base)}
                        <div className="muted small">{fmtPct(s.cost.cost_pct)}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="row gap-sm">
                <button className="btn-ghost small" onClick={() => setEditing(r)}>
                  Editar
                </button>
                <button
                  className="btn-ghost small danger"
                  onClick={() => confirmDelete("esta ruta y todos sus pasos") && remove.mutate(r.id)}
                >
                  Borrar
                </button>
              </div>
            </details>
          ))}
        </div>
      )}
      <ErrorText error={remove.error} />
    </>
  );
}

function chainLabel(r: Route, name: (id: number) => string): string {
  if (!r.steps.length) return "Ruta vacía";
  return [name(r.steps[0].from_account_id), ...r.steps.map((s) => name(s.to_account_id))].join(" → ");
}

function emptyStep(from = 0, to = 0, amountOut = ""): TransferStepInput {
  return {
    from_account_id: from,
    to_account_id: to,
    amount_out: amountOut,
    amount_in: "",
    fee_amount: "0",
    fee_account_id: from || null,
    ref_rate_out: null,
    ref_rate_in: null,
    occurred_on: null,
    notes: null,
  };
}

function RouteForm({
  route,
  accounts,
  base,
  onDone,
}: {
  route: Route | null;
  accounts: Account[];
  base: string;
  onDone: () => void;
}) {
  const save = useSaveRoute();
  const [name, setName] = useState(route?.name ?? "");
  const [date, setDate] = useState(route?.started_on ?? today());
  const [showRates, setShowRates] = useState(false);
  const [steps, setSteps] = useState<TransferStepInput[]>(() =>
    route
      ? route.steps.map((s) => ({
          from_account_id: s.from_account_id,
          to_account_id: s.to_account_id,
          amount_out: plain(s.amount_out),
          amount_in: plain(s.amount_in),
          fee_amount: plain(s.fee_amount) || "0",
          fee_account_id: s.fee_account_id,
          ref_rate_out: s.ref_rate_out ? plain(s.ref_rate_out) : null,
          ref_rate_in: s.ref_rate_in ? plain(s.ref_rate_in) : null,
          occurred_on: s.occurred_on,
          notes: s.notes,
        }))
      : [emptyStep(accounts[0]?.id, accounts[1]?.id)],
  );

  if (accounts.length < 2) {
    return <Empty>Necesitas al menos dos plataformas para registrar movimientos P2P.</Empty>;
  }

  const currency = (id: number) => accounts.find((a) => a.id === id)?.currency ?? "";
  const update = (i: number, patch: Partial<TransferStepInput>) =>
    setSteps((all) =>
      all.map((s, j) => {
        if (j !== i) return s;
        // Fee platform follows the source platform while they were the same.
        const follow = patch.from_account_id !== undefined && s.fee_account_id === s.from_account_id;
        return { ...s, ...patch, ...(follow ? { fee_account_id: patch.from_account_id } : {}) };
      }),
    );

  function addStep() {
    // Next step starts where the previous one ended, with what arrived.
    const last = steps[steps.length - 1];
    const next = accounts.find((a) => a.id !== last.to_account_id)?.id ?? 0;
    setSteps([...steps, emptyStep(last.to_account_id, next, last.amount_in)]);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = {
      name: name || null,
      started_on: date,
      notes: null,
      steps: steps.map((s) => ({
        ...s,
        fee_amount: s.fee_amount || "0",
        ref_rate_out: s.ref_rate_out || null,
        ref_rate_in: s.ref_rate_in || null,
        occurred_on: s.occurred_on || null,
      })),
    };
    save.mutate(route ? { ...body, id: route.id } : body, {
      onSuccess: () => {
        setName("");
        setSteps([emptyStep(accounts[0]?.id, accounts[1]?.id)]);
        onDone();
      },
    });
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <div className="row-between">
        <h2>{route ? "Editar ruta" : "Registrar movimiento P2P"}</h2>
        <label className="row gap-sm small muted toggle">
          <input type="checkbox" checked={showRates} onChange={(e) => setShowRates(e.target.checked)} />
          Tasas de referencia por paso
        </label>
      </div>
      <p className="muted small">
        Un paso por cada salto (ej. Facebank → Binance, Binance → Nequi). “Envié” incluye la comisión; “Recibí” es
        lo que llegó. El costo real se calcula contra tus tasas de referencia en {base}.
      </p>
      <div className="grid-2">
        <label>
          Nombre (opcional)
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Sueldo a Nequi" />
        </label>
        <label>
          Fecha
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
      </div>

      {steps.map((s, i) => (
        <fieldset key={i} className="step">
          <legend>Paso {i + 1}</legend>
          <div className="grid-5">
            <label>
              Desde
              <AccountSelect accounts={accounts} value={s.from_account_id} onChange={(v) => update(i, { from_account_id: v })} />
            </label>
            <label>
              Hacia
              <AccountSelect accounts={accounts} value={s.to_account_id} onChange={(v) => update(i, { to_account_id: v })} />
            </label>
            <label>
              Envié ({currency(s.from_account_id)})
              <input
                type="number"
                step="any"
                min="0"
                value={s.amount_out}
                onChange={(e) => update(i, { amount_out: e.target.value })}
                required
              />
            </label>
            <label>
              Recibí ({currency(s.to_account_id)})
              <input
                type="number"
                step="any"
                min="0"
                value={s.amount_in}
                onChange={(e) => update(i, { amount_in: e.target.value })}
                required
              />
            </label>
            <label>
              Comisión ({currency(s.fee_account_id ?? s.from_account_id)})
              <input
                type="number"
                step="any"
                min="0"
                value={s.fee_amount}
                onChange={(e) => update(i, { fee_amount: e.target.value })}
              />
            </label>
          </div>
          <label>
            Comisión se cobra desde (se suma a lo que envías)
            <select
              value={s.fee_account_id ?? ""}
              onChange={(e) => update(i, { fee_account_id: e.target.value ? Number(e.target.value) : null })}
            >
              {s.fee_account_id === null && <option value="">Incluida en lo que envío (dato anterior)</option>}
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
          </label>
          {showRates && (
            <div className="grid-3">
              <label>
                Tasa ref. {currency(s.from_account_id)}
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={s.ref_rate_out ?? ""}
                  onChange={(e) => update(i, { ref_rate_out: e.target.value || null })}
                  placeholder={`por 1 ${base}`}
                />
              </label>
              <label>
                Tasa ref. {currency(s.to_account_id)}
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={s.ref_rate_in ?? ""}
                  onChange={(e) => update(i, { ref_rate_in: e.target.value || null })}
                  placeholder={`por 1 ${base}`}
                />
              </label>
              <label>
                Fecha del paso
                <input
                  type="date"
                  value={s.occurred_on ?? ""}
                  onChange={(e) => update(i, { occurred_on: e.target.value || null })}
                />
              </label>
            </div>
          )}
          {steps.length > 1 && (
            <button type="button" className="link danger" onClick={() => setSteps(steps.filter((_, j) => j !== i))}>
              Quitar paso
            </button>
          )}
        </fieldset>
      ))}

      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button type="button" className="btn-ghost" onClick={addStep}>
          + Agregar paso
        </button>
        <button className="btn" disabled={save.isPending}>
          {route ? "Guardar ruta" : "Registrar"}
        </button>
        {route && (
          <button type="button" className="btn-ghost" onClick={onDone}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

function AccountSelect({
  accounts,
  value,
  onChange,
}: {
  accounts: Account[];
  value: number;
  onChange: (id: number) => void;
}) {
  return (
    <select value={value || ""} onChange={(e) => onChange(Number(e.target.value))} required>
      <option value="" disabled>
        Elige…
      </option>
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name} ({a.currency})
        </option>
      ))}
    </select>
  );
}
