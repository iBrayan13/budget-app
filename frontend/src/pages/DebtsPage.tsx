import { FormEvent, useState } from "react";
import { useAccounts, useDebtPayment, useDebts, useDeleteDebt, useSaveDebt } from "../api/hooks";
import type { Debt, DebtInput, DebtKind, DebtSchedule } from "../api/types";
import { describeRule, FrequencyPicker, SchedulePreview } from "../components/Frequency";
import { confirmDelete, Empty, ErrorText, Tile } from "../components/ui";
import { CURRENCIES, fmtMoney, fmtPct, plain, today } from "../lib/format";

const KIND_LABEL: Record<DebtKind, string> = {
  installment_loan: "Préstamo a cuotas",
  credit_card: "Tarjeta de crédito",
  informal: "Deuda informal",
};

export default function DebtsPage() {
  const [showInactive, setShowInactive] = useState(false);
  const { data, isLoading } = useDebts(showInactive);
  const [editing, setEditing] = useState<Debt | null>(null);
  const base = data?.base_currency ?? "USD";
  const overLimit = data?.debt_ratio_pct != null && Number(data.debt_ratio_pct) > Number(data.max_ratio_pct);

  return (
    <>
      <header className="page-header">
        <h1>Deudas</h1>
        <label className="row gap-sm small muted toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar archivadas
        </label>
      </header>

      <section className="tiles">
        <Tile label="Deuda total" value={fmtMoney(data?.total_balance_base, base)} />
        <Tile label="Cuotas al mes" value={fmtMoney(data?.monthly_payments_base, base)} />
        <Tile
          label="Nivel de endeudamiento"
          value={<span className={overLimit ? "danger" : ""}>{fmtPct(data?.debt_ratio_pct)}</span>}
          hint={
            data?.avg_monthly_income_base
              ? `de ${fmtMoney(data.avg_monthly_income_base, base)} de ingreso · máx. ${fmtPct(data.max_ratio_pct)}`
              : "registra ingresos para calcularlo"
          }
        />
        <Tile
          label="Capacidad de endeudamiento"
          value={fmtMoney(data?.capacity_base, base)}
          hint="cuota mensual adicional que podrías asumir"
        />
      </section>

      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : !data?.items.length ? (
        <Empty>No tienes deudas registradas. 🎉</Empty>
      ) : (
        <div className="stack">
          {data.items.map((d) => (
            <DebtCard key={d.id} d={d} base={base} onEdit={() => setEditing(d)} />
          ))}
        </div>
      )}

      <DebtForm key={editing?.id ?? "new"} editing={editing} onDone={() => setEditing(null)} />
    </>
  );
}

function DebtCard({ d, base, onEdit }: { d: Debt; base: string; onEdit: () => void }) {
  const [paying, setPaying] = useState(false);
  const remove = useDeleteDebt();
  const save = useSaveDebt();

  function toggleActive() {
    save.mutate({ ...toInput(d), is_active: !d.is_active, id: d.id });
  }

  return (
    <div className={`card debt ${d.is_active ? "" : "archived"}`}>
      <div className="row-between">
        <div>
          <strong>{d.name}</strong> <span className="badge">{KIND_LABEL[d.kind]}</span>
          <div className="muted small">
            {d.creditor && `${d.creditor} · `}
            {d.interest_rate_annual && `${fmtPct(d.interest_rate_annual)} anual · `}
            desde {d.start_date}
          </div>
        </div>
        <div className="num">
          <div className="tile-value">{fmtMoney(d.balance, d.currency)}</div>
          {d.currency !== base && <div className="muted small">≈ {fmtMoney(d.balance_base, base)}</div>}
        </div>
      </div>

      <div className="progress" title={`${fmtPct(d.progress_pct)} pagado`}>
        <div style={{ width: `${Number(d.progress_pct)}%` }} />
      </div>

      <div className="facts">
        <span>
          Original <strong>{fmtMoney(d.original_amount, d.currency)}</strong>
        </span>
        <span>
          Pagado <strong>{fmtMoney(d.paid_total, d.currency)}</strong> ({d.payments_count} pagos)
        </span>
        {d.installment_amount && d.schedule_rrule && (
          <span>
            Cuota <strong>{fmtMoney(d.installment_amount, d.currency)}</strong> · {describeRule(d.schedule_rrule).toLowerCase()}
          </span>
        )}
        {d.remaining_installments !== null && (
          <span>
            Faltan <strong>{d.remaining_installments}</strong> de {d.installments_total} cuotas
          </span>
        )}
        {d.next_due_date && (
          <span>
            Próxima <strong>{d.next_due_date}</strong>
          </span>
        )}
        {d.end_date && (
          <span>
            Termina <strong>{d.end_date}</strong>
          </span>
        )}
        {d.total_interest && (
          <span>
            Intereses totales <strong>{fmtMoney(d.total_interest, d.currency)}</strong>
          </span>
        )}
      </div>
      {d.kind === "installment_loan" && d.interest_rate_annual && (
        <p className="muted small">El saldo de un préstamo con interés es estimado (amortización de cuota fija).</p>
      )}

      <div className="row gap-sm">
        <button className="btn-ghost small" onClick={() => setPaying(!paying)}>
          {d.kind === "credit_card" ? "Pagar tarjeta" : "Abonar"}
        </button>
        <button className="btn-ghost small" onClick={onEdit}>
          Editar
        </button>
        <button className="btn-ghost small" onClick={toggleActive}>
          {d.is_active ? "Archivar" : "Reactivar"}
        </button>
        <button
          className="btn-ghost small danger"
          onClick={() =>
            confirmDelete(`${d.name} y su plan de cuotas (los pagos hechos se conservan)`) && remove.mutate(d.id)
          }
        >
          Borrar
        </button>
      </div>
      <ErrorText error={remove.error ?? save.error} />
      {paying && <PaymentForm d={d} onDone={() => setPaying(false)} />}
    </div>
  );
}

function PaymentForm({ d, onDone }: { d: Debt; onDone: () => void }) {
  const { data } = useAccounts();
  const pay = useDebtPayment();
  const accounts = (data?.accounts ?? []).filter((a) => a.id !== d.account_id);
  const [accountId, setAccountId] = useState(d.schedule_account_id ?? 0);
  const account = accounts.find((a) => a.id === accountId) ?? accounts[0];
  const [amount, setAmount] = useState("");
  const [amountIn, setAmountIn] = useState("");
  const [date, setDate] = useState(today());
  const needsAmountIn = d.kind === "credit_card" && account && account.currency !== d.currency;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!account) return;
    pay.mutate(
      { id: d.id, account_id: account.id, amount, amount_in: amountIn || null, occurred_on: date },
      { onSuccess: onDone },
    );
  }

  return (
    <form className="grid-4 pay-form" onSubmit={onSubmit}>
      <label>
        Desde
        <select value={account?.id ?? ""} onChange={(e) => setAccountId(Number(e.target.value))}>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.currency})
            </option>
          ))}
        </select>
      </label>
      <label>
        Monto ({account?.currency})
        <input type="number" step="any" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} required />
      </label>
      {needsAmountIn ? (
        <label>
          Llegó a la tarjeta ({d.currency})
          <input
            type="number"
            step="any"
            min="0"
            value={amountIn}
            onChange={(e) => setAmountIn(e.target.value)}
            required
          />
        </label>
      ) : (
        <label>
          Fecha
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
      )}
      <div className="row gap-sm">
        <button className="btn" disabled={pay.isPending}>
          Registrar
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Cancelar
        </button>
      </div>
      <ErrorText error={pay.error} />
    </form>
  );
}

function toInput(d: Debt): DebtInput {
  return {
    name: d.name,
    kind: d.kind,
    creditor: d.creditor,
    currency: d.currency,
    original_amount: plain(d.original_amount),
    interest_rate_annual: d.interest_rate_annual ? plain(d.interest_rate_annual) : null,
    start_date: d.start_date,
    account_id: d.account_id,
    is_active: d.is_active,
    notes: d.notes,
    schedule:
      d.installment_amount && d.schedule_rrule
        ? {
            installment_amount: plain(d.installment_amount),
            rrule: d.schedule_rrule,
            first_due_date: d.schedule_first_due_date ?? d.start_date,
            installments_total: d.installments_total,
            account_id: d.schedule_account_id,
          }
        : null,
  };
}

function emptySchedule(): DebtSchedule {
  return { installment_amount: "", rrule: "FREQ=MONTHLY", first_due_date: today(), installments_total: null, account_id: null };
}

function blank(): DebtInput {
  return {
    name: "",
    kind: "installment_loan",
    creditor: null,
    currency: "COP",
    original_amount: "",
    interest_rate_annual: null,
    start_date: today(),
    account_id: null,
    schedule: emptySchedule(),
    is_active: true,
    notes: null,
  };
}

function DebtForm({ editing, onDone }: { editing: Debt | null; onDone: () => void }) {
  const { data: accountsData } = useAccounts(true);
  const save = useSaveDebt();
  const [form, setForm] = useState<DebtInput>(() => (editing ? toInput(editing) : blank()));
  const set = <K extends keyof DebtInput>(k: K, v: DebtInput[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setSched = <K extends keyof DebtSchedule>(k: K, v: DebtSchedule[K]) =>
    setForm((f) => ({ ...f, schedule: { ...(f.schedule ?? emptySchedule()), [k]: v } }));
  const accounts = accountsData?.accounts ?? [];
  const cards = accounts.filter((a) => a.kind === "credit_card");

  function setKind(kind: DebtKind) {
    setForm((f) => ({
      ...f,
      kind,
      schedule: kind === "installment_loan" ? (f.schedule ?? emptySchedule()) : kind === "informal" ? null : f.schedule,
      account_id: kind === "credit_card" ? f.account_id : null,
    }));
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body: DebtInput = {
      ...form,
      creditor: form.creditor || null,
      interest_rate_annual: form.interest_rate_annual || null,
      notes: form.notes || null,
    };
    save.mutate(editing ? { ...body, id: editing.id } : body, {
      onSuccess: () => {
        setForm(blank());
        onDone();
      },
    });
  }

  const s = form.schedule;
  return (
    <form className="card form" onSubmit={onSubmit}>
      <div className="row-between">
        <h2>{editing ? `Editar ${editing.name}` : "Nueva deuda"}</h2>
        <div className="tabs" role="tablist">
          {(Object.keys(KIND_LABEL) as DebtKind[]).map((k) => (
            <button
              type="button"
              key={k}
              role="tab"
              aria-selected={form.kind === k}
              className={form.kind === k ? "tab active" : "tab"}
              onClick={() => setKind(k)}
            >
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid-4">
        <label>
          Nombre
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={120} />
        </label>
        <label>
          Acreedor
          <input
            value={form.creditor ?? ""}
            onChange={(e) => set("creditor", e.target.value)}
            placeholder={form.kind === "informal" ? "Ej. mi hermano" : "Ej. Bancolombia"}
          />
        </label>
        <label>
          {form.kind === "credit_card" ? "Cupo usado al registrar" : "Monto prestado"}
          <input
            type="number"
            step="any"
            min="0"
            value={form.original_amount}
            onChange={(e) => set("original_amount", e.target.value)}
            required
          />
        </label>
        <div className="grid-2">
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
          <label>
            Interés anual %
            <input
              type="number"
              step="any"
              min="0"
              value={form.interest_rate_annual ?? ""}
              onChange={(e) => set("interest_rate_annual", e.target.value || null)}
            />
          </label>
        </div>
      </div>

      <div className="grid-3">
        <label>
          Fecha de la deuda
          <input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required />
        </label>
        {form.kind === "credit_card" && (
          <label>
            Plataforma de la tarjeta
            <select value={form.account_id ?? ""} onChange={(e) => set("account_id", Number(e.target.value) || null)} required>
              <option value="">Elige…</option>
              {cards.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
            {cards.length === 0 && (
              <span className="muted small">Crea primero la tarjeta en Plataformas con tipo “Tarjeta de crédito”.</span>
            )}
          </label>
        )}
        {form.kind !== "installment_loan" && (
          <label className="row gap-sm toggle">
            <input
              type="checkbox"
              checked={!!s}
              onChange={(e) => set("schedule", e.target.checked ? emptySchedule() : null)}
            />
            {form.kind === "credit_card" ? "Tiene pago mínimo fijo" : "Tiene cuotas fijas"}
          </label>
        )}
      </div>

      {s && (
        <fieldset className="step">
          <legend>Plan de cuotas (se agrega a Gastos fijos como esencial)</legend>
          <div className="grid-4">
            <label>
              Cuota ({form.currency})
              <input
                type="number"
                step="any"
                min="0"
                value={s.installment_amount}
                onChange={(e) => setSched("installment_amount", e.target.value)}
                required
              />
            </label>
            <label>
              Primera cuota
              <input
                type="date"
                value={s.first_due_date}
                onChange={(e) => setSched("first_due_date", e.target.value)}
                required
              />
            </label>
            <label>
              Número de cuotas
              <input
                type="number"
                min="1"
                value={s.installments_total ?? ""}
                onChange={(e) => setSched("installments_total", e.target.value ? Number(e.target.value) : null)}
                placeholder="sin límite"
              />
            </label>
            <label>
              Se paga desde
              <select
                value={s.account_id ?? ""}
                onChange={(e) => setSched("account_id", Number(e.target.value) || null)}
              >
                <option value="">(sin definir)</option>
                {accounts
                  .filter((a) => a.kind !== "credit_card")
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.currency})
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <FrequencyPicker value={s.rrule} onChange={(r) => setSched("rrule", r)} />
          <SchedulePreview rule={s.rrule} start={s.first_due_date} end={null} />
        </fieldset>
      )}
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          {editing ? "Guardar" : "Registrar deuda"}
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
