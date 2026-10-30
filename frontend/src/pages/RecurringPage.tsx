import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  useAccounts,
  useCategories,
  useDeleteRecurring,
  useObligationAction,
  useObligations,
  usePayObligation,
  useRecurring,
  useSaveRecurring,
  useSeedCategories,
} from "../api/hooks";
import type { Account, Obligation, RecurringExpense, RecurringInput } from "../api/types";
import { describeRule, FrequencyPicker, SchedulePreview } from "../components/Frequency";
import { confirmDelete, Empty, ErrorText, MonthPicker, Tile } from "../components/ui";
import { CURRENCIES, currentMonth, fmtMoney, monthRange, plain, today } from "../lib/format";

const STATUS_LABEL = { pending: "Pendiente", paid: "Pagado", skipped: "Omitido" } as const;

export default function RecurringPage() {
  const [month, setMonth] = useState(currentMonth());
  const [editing, setEditing] = useState<RecurringExpense | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const { data: summary } = useRecurring(showInactive);
  const { data: obligations, isLoading } = useObligations({ ...monthRange(month), include_overdue: true });
  const { data: categories } = useCategories(true);
  const remove = useDeleteRecurring();
  const base = summary?.base_currency ?? "USD";
  const catName = (id: number) => categories?.find((c) => c.id === id)?.name ?? "";

  const pending = (obligations ?? []).filter((o) => o.status === "pending");
  const pendingBase = pending.reduce((sum, o) => sum + Number(o.expected_base ?? 0), 0);
  const overdue = pending.filter((o) => o.is_overdue);

  return (
    <>
      <header className="page-header">
        <h1>Gastos fijos</h1>
        <MonthPicker value={month} onChange={setMonth} />
      </header>

      <section className="tiles">
        <Tile label="Fijos al mes" value={fmtMoney(summary?.monthly_total_base, base)} hint="equivalente mensual" />
        <Tile label="Esenciales" value={fmtMoney(summary?.monthly_essential_base, base)} hint="cuentan para sobrevivir" />
        <Tile label="Estilo de vida" value={fmtMoney(summary?.monthly_lifestyle_base, base)} />
        <Tile
          label="Por pagar en el mes"
          value={fmtMoney(pendingBase, base)}
          hint={`${pending.length} pago(s)${overdue.length ? ` · ${overdue.length} vencido(s)` : ""}`}
        />
      </section>
      {summary && summary.without_rate.length > 0 && (
        <p className="warning">Sin tasa de referencia, no se suman: {summary.without_rate.join(", ")}.</p>
      )}

      <h2>Calendario de pagos</h2>
      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : !obligations?.length ? (
        <Empty>No hay pagos programados en este mes.</Empty>
      ) : (
        <div className="card table-wrap">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Gasto</th>
                <th className="num">Monto</th>
                <th>Estado</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {obligations.map((o) => (
                <ObligationRow key={o.id} o={o} base={base} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="row-between">
        <h2>Mis gastos fijos</h2>
        <label className="row gap-sm small muted toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar inactivos
        </label>
      </div>
      {!summary?.items.length ? (
        <Empty>Aún no tienes gastos fijos. Agrega el primero abajo (arriendo, servicios, suscripciones…).</Empty>
      ) : (
        <div className="card table-wrap">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>Gasto</th>
                <th>Frecuencia</th>
                <th className="num">Monto</th>
                <th className="num">Al mes ({base})</th>
                <th>Próximo</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {summary.items.map((e) => (
                <tr key={e.id} className={e.is_active ? "" : "archived"}>
                  <td data-label="Gasto">
                    {e.name}
                    <div className="muted small">
                      {catName(e.category_id)} · {e.level === "essential" ? "esencial" : "estilo de vida"}
                    </div>
                  </td>
                  <td data-label="Frecuencia">{describeRule(e.rrule)}</td>
                  <td data-label="Monto" className="num">{fmtMoney(e.amount, e.currency)}</td>
                  <td data-label="Al mes" className="num">{fmtMoney(e.monthly_amount_base, base)}</td>
                  <td data-label="Próximo">{e.next_due_date ?? "—"}</td>
                  <td data-label="" className="num nowrap">
                    {e.debt_id ? (
                      <Link to="/deudas" className="link small">
                        Ver deuda
                      </Link>
                    ) : (
                      <>
                        <button className="link small" onClick={() => setEditing(e)}>
                          Editar
                        </button>{" "}
                        <button
                          className="link small danger"
                          onClick={() =>
                            confirmDelete(`${e.name} y su calendario (los pagos hechos se conservan)`) &&
                            remove.mutate(e.id)
                          }
                        >
                          Borrar
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ErrorText error={remove.error} />

      <RecurringForm key={editing?.id ?? "new"} editing={editing} onDone={() => setEditing(null)} />
    </>
  );
}

function ObligationRow({ o, base }: { o: Obligation; base: string }) {
  const [paying, setPaying] = useState(false);
  const action = useObligationAction();

  return (
    <>
      <tr className={o.status === "skipped" ? "archived" : ""}>
        <td data-label="Fecha" className={o.is_overdue ? "danger" : ""}>{o.due_date}</td>
        <td data-label="Gasto">
          {o.name}
          {o.debt_id && <span className="badge">deuda</span>}
        </td>
        <td data-label="Monto" className="num">
          {fmtMoney(o.status === "paid" ? o.paid_amount : o.expected_amount, o.status === "paid" ? o.paid_currency! : o.currency)}
          {o.currency !== base && o.status !== "paid" && (
            <div className="muted small">≈ {fmtMoney(o.expected_base, base)}</div>
          )}
        </td>
        <td data-label="Estado">
          <span className={`badge status-${o.is_overdue ? "overdue" : o.status}`}>
            {o.is_overdue ? "Vencido" : STATUS_LABEL[o.status]}
          </span>
        </td>
        <td data-label="" className="num nowrap">
          {o.status === "pending" ? (
            <>
              <button className="link small" onClick={() => setPaying(!paying)}>
                Pagar
              </button>{" "}
              <button
                className="link small muted"
                title="No se pagará (ya estaba pagado antes de usar la app, se condonó…)"
                onClick={() => action.mutate({ id: o.id, action: "skip" })}
              >
                Omitir
              </button>
            </>
          ) : (
            <button
              className="link small"
              title={o.status === "paid" ? "Borra el movimiento del pago" : undefined}
              onClick={() =>
                (o.status !== "paid" || confirmDelete("el movimiento de este pago")) &&
                action.mutate({ id: o.id, action: "reopen" })
              }
            >
              Reabrir
            </button>
          )}
          <ErrorText error={action.error} />
        </td>
      </tr>
      {paying && (
        <tr>
          <td colSpan={5}>
            <PayForm o={o} onDone={() => setPaying(false)} />
          </td>
        </tr>
      )}
    </>
  );
}

function PayForm({ o, onDone }: { o: Obligation; onDone: () => void }) {
  const { data } = useAccounts();
  const pay = usePayObligation();
  const accounts = data?.accounts ?? [];
  const [accountId, setAccountId] = useState<number>(o.account_id ?? accounts[0]?.id ?? 0);
  const account = accounts.find((a) => a.id === (accountId || accounts[0]?.id));
  const sameCurrency = account?.currency === o.currency;
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!account) return;
    pay.mutate(
      { id: o.id, account_id: account.id, amount: amount || null, occurred_on: date },
      { onSuccess: onDone },
    );
  }

  return (
    <form className="grid-4 pay-form" onSubmit={onSubmit}>
      <label>
        Pagar desde
        <AccountSelect accounts={accounts} value={account?.id ?? 0} onChange={setAccountId} />
      </label>
      <label>
        Monto {account && `(${account.currency})`}
        <input
          type="number"
          step="any"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder={sameCurrency ? plain(o.expected_amount) : `cuánto salió en ${account?.currency ?? ""}`}
          required={!sameCurrency}
        />
      </label>
      <label>
        Fecha
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <div className="row gap-sm">
        <button className="btn" disabled={pay.isPending}>
          Registrar pago
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Cancelar
        </button>
      </div>
      <ErrorText error={pay.error} />
    </form>
  );
}

function AccountSelect({
  accounts,
  value,
  onChange,
  allowEmpty,
}: {
  accounts: Account[];
  value: number | null;
  onChange: (id: number) => void;
  allowEmpty?: string;
}) {
  return (
    <select value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))}>
      {allowEmpty !== undefined && <option value="">{allowEmpty}</option>}
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name} ({a.currency})
        </option>
      ))}
    </select>
  );
}

function blank(): RecurringInput {
  return {
    name: "",
    category_id: 0,
    account_id: null,
    amount: "",
    currency: "USD",
    rrule: "FREQ=MONTHLY",
    start_date: today(),
    end_date: null,
    is_active: true,
    notes: null,
  };
}

function RecurringForm({ editing, onDone }: { editing: RecurringExpense | null; onDone: () => void }) {
  const { data: accountsData } = useAccounts();
  const { data: categories } = useCategories();
  const save = useSaveRecurring();
  const seedCategories = useSeedCategories();
  const [form, setForm] = useState<RecurringInput>(() =>
    editing
      ? {
          name: editing.name,
          category_id: editing.category_id,
          account_id: editing.account_id,
          amount: plain(editing.amount),
          currency: editing.currency,
          rrule: editing.rrule,
          start_date: editing.start_date,
          end_date: editing.end_date,
          is_active: editing.is_active,
          notes: editing.notes,
        }
      : blank(),
  );
  const set = <K extends keyof RecurringInput>(k: K, v: RecurringInput[K]) => setForm((f) => ({ ...f, [k]: v }));
  const accounts = accountsData?.accounts ?? [];
  const expenseCats = useMemo(() => (categories ?? []).filter((c) => c.kind === "expense"), [categories]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = { ...form, end_date: form.end_date || null, notes: form.notes || null };
    save.mutate(editing ? { ...body, id: editing.id } : body, {
      onSuccess: () => {
        setForm(blank());
        onDone();
      },
    });
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h2>{editing ? `Editar ${editing.name}` : "Nuevo gasto fijo"}</h2>
      {expenseCats.length === 0 && (
        <div className="warning row-between">
          <span>Aún no tienes categorías de gasto. Carga las sugeridas para elegir una.</span>
          <button type="button" className="btn-ghost small" onClick={() => seedCategories.mutate()}>
            Cargar categorías
          </button>
        </div>
      )}
      <div className="grid-4">
        <label>
          Nombre
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={120} />
        </label>
        <label>
          Categoría
          <select value={form.category_id || ""} onChange={(e) => set("category_id", Number(e.target.value))} required>
            <option value="" disabled>
              Elige…
            </option>
            <optgroup label="Esenciales (sobrevivir)">
              {expenseCats
                .filter((c) => c.level === "essential")
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </optgroup>
            <optgroup label="Estilo de vida">
              {expenseCats
                .filter((c) => c.level === "lifestyle")
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </optgroup>
          </select>
        </label>
        <label>
          Se paga normalmente desde
          <AccountSelect
            accounts={accounts}
            value={form.account_id}
            allowEmpty="(sin definir)"
            onChange={(id) => {
              const acc = accounts.find((a) => a.id === id);
              setForm((f) => ({ ...f, account_id: id || null, currency: acc?.currency ?? f.currency }));
            }}
          />
        </label>
        <div className="grid-2">
          <label>
            Monto
            <input
              type="number"
              step="any"
              min="0"
              value={form.amount}
              onChange={(e) => set("amount", e.target.value)}
              required
            />
          </label>
          <label>
            Moneda
            <select value={form.currency} onChange={(e) => set("currency", e.target.value)} required>
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <FrequencyPicker value={form.rrule} onChange={(r) => set("rrule", r)} />
      <div className="grid-3">
        <label>
          Primer pago a seguir
          <input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required />
        </label>
        <label>
          Termina (opcional)
          <input type="date" value={form.end_date ?? ""} onChange={(e) => set("end_date", e.target.value || null)} />
        </label>
        <label className="row gap-sm toggle">
          <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
          Activo
        </label>
      </div>
      <SchedulePreview rule={form.rrule} start={form.start_date} end={form.end_date} />
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          {editing ? "Guardar" : "Crear gasto fijo"}
        </button>
        {editing && (
          <button type="button" className="btn-ghost" onClick={onDone}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
