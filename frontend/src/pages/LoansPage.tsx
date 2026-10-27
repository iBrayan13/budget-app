import { FormEvent, useState } from "react";
import {
  useAccounts,
  useDeleteLoan,
  useDeleteLoanPayment,
  useLoanPayment,
  useLoans,
  useSaveLoan,
} from "../api/hooks";
import type { Loan } from "../api/types";
import { useMe } from "../auth/useAuth";
import { confirmDelete, Empty, ErrorText, Progress, Tile } from "../components/ui";
import { fmtMoney, plain, today } from "../lib/format";

export default function LoansPage() {
  const { data: user } = useMe();
  const { data, isLoading } = useLoans();
  const base = user?.base_currency ?? "USD";
  const m = (v: string | null | undefined, c?: string) => fmtMoney(v, c ?? base);

  const items = data?.items ?? [];
  const lent = items.reduce((sum, l) => sum + Number(l.principal), 0);
  const collected = items.reduce((sum, l) => sum + Number(l.paid), 0);

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Préstamos 🤝</h1>
          <span className="muted">Lo que prestaste y te deben. No cuenta como gasto ni como ingreso.</span>
        </div>
      </header>

      <section className="tiles">
        <Tile label="Te deben" value={m(data?.total_balance_base)} hint="en tu moneda base" />
        <Tile label="Prestado en total" value={m(String(lent))} hint="suma de los montos originales" />
        <Tile label="Ya cobrado" value={m(String(collected))} />
      </section>

      <NewLoanForm />

      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : items.length === 0 ? (
        <Empty>Aún no tienes préstamos. Cuando le prestes a alguien, regístralo aquí.</Empty>
      ) : (
        <div className="stack">
          {items.map((l) => (
            <LoanCard key={l.id} loan={l} base={base} />
          ))}
        </div>
      )}
    </>
  );
}

function LoanCard({ loan, base }: { loan: Loan; base: string }) {
  const [paying, setPaying] = useState(false);
  const [showPayments, setShowPayments] = useState(false);
  const remove = useDeleteLoan();
  const removePayment = useDeleteLoanPayment();

  return (
    <div className="card goal-card">
      <div className="row-between">
        <div>
          <strong>{loan.borrower}</strong>
          <div className="muted small">
            Prestado el {loan.start_date} desde {loan.account_name}
            {loan.due_date && ` · cobrar antes del ${loan.due_date}`}
          </div>
        </div>
        <div className="num">
          <div className="tile-value">{fmtMoney(loan.balance, loan.currency)}</div>
          <div className="muted small">
            {loan.currency !== base ? `≈ ${fmtMoney(loan.balance_base, base)} · ` : ""}de {fmtMoney(loan.principal, loan.currency)}
          </div>
        </div>
      </div>
      <Progress pct={loan.progress_pct} />
      {loan.notes && <p className="muted small">{loan.notes}</p>}

      <div className="row gap-sm">
        <button className="btn-ghost small" onClick={() => setPaying(!paying)}>
          Registrar cobro
        </button>
        <button className="btn-ghost small" onClick={() => setShowPayments(!showPayments)}>
          Ver cobros ({loan.payments.length})
        </button>
        <button
          className="btn-ghost small danger"
          onClick={() =>
            confirmDelete(`el préstamo a ${loan.borrower} (el dinero vuelve a su plataforma)`) && remove.mutate(loan.id)
          }
        >
          Borrar
        </button>
      </div>
      <ErrorText error={remove.error} />

      {paying && <PaymentForm loan={loan} onDone={() => setPaying(false)} />}
      {showPayments && (
        <div className="table-wrap">
          {loan.payments.length === 0 ? (
            <p className="muted small">Aún no te han pagado nada.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Llegó a</th>
                  <th className="num">Monto</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {loan.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{p.occurred_on}</td>
                    <td>{p.account_name}</td>
                    <td className="num">{fmtMoney(p.amount, loan.currency)}</td>
                    <td className="num">
                      <button
                        className="link danger"
                        onClick={() => confirmDelete("este cobro") && removePayment.mutate(p.id)}
                      >
                        Quitar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <ErrorText error={removePayment.error} />
        </div>
      )}
    </div>
  );
}

function PaymentForm({ loan, onDone }: { loan: Loan; onDone: () => void }) {
  const { data } = useAccounts();
  const pay = useLoanPayment();
  // Only platforms in the loan's currency can receive the money back.
  const accounts = (data?.accounts ?? []).filter((a) => a.currency === loan.currency);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const account = accounts.find((a) => a.id === (accountId ?? accounts[0]?.id));

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!account) return;
    pay.mutate(
      { loanId: loan.id, account_id: account.id, amount, occurred_on: date },
      { onSuccess: () => { setAmount(""); onDone(); } },
    );
  }

  if (accounts.length === 0)
    return <p className="warning">Necesitas una plataforma en {loan.currency} para recibir el cobro.</p>;

  return (
    <form className="grid-4 pay-form" onSubmit={onSubmit}>
      <label>
        Llegó a
        <select value={account?.id ?? ""} onChange={(e) => setAccountId(Number(e.target.value))}>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.currency})
            </option>
          ))}
        </select>
      </label>
      <label>
        Monto ({loan.currency})
        <input
          type="number"
          step="any"
          min="0"
          max={plain(loan.balance)}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
      </label>
      <label>
        Fecha
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
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

function NewLoanForm() {
  const { data } = useAccounts();
  const save = useSaveLoan();
  const accounts = data?.accounts ?? [];
  const blank = { borrower: "", account_id: 0, amount: "", start_date: today(), due_date: "", notes: "" };
  const [form, setForm] = useState(blank);
  const set = <K extends keyof typeof blank>(k: K, v: (typeof blank)[K]) => setForm((f) => ({ ...f, [k]: v }));
  const from = accounts.find((a) => a.id === (form.account_id || accounts[0]?.id));

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate(
      {
        borrower: form.borrower,
        account_id: from?.id ?? 0,
        amount: form.amount,
        start_date: form.start_date,
        due_date: form.due_date || null,
        notes: form.notes || null,
      },
      { onSuccess: () => setForm({ ...blank, account_id: form.account_id }) },
    );
  }

  if (accounts.length === 0) return <Empty>Crea una plataforma primero para poder prestar desde ella.</Empty>;

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h2>Nuevo préstamo</h2>
      <div className="grid-4">
        <label>
          ¿A quién le prestaste?
          <input value={form.borrower} onChange={(e) => set("borrower", e.target.value)} required maxLength={120} />
        </label>
        <label>
          Sale de
          <select value={from?.id ?? ""} onChange={(e) => set("account_id", Number(e.target.value))}>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </select>
        </label>
        <label>
          Monto {from && `(${from.currency})`}
          <input type="number" step="any" min="0" value={form.amount} onChange={(e) => set("amount", e.target.value)} required />
        </label>
        <label>
          Fecha
          <input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required />
        </label>
      </div>
      <div className="grid-3">
        <label>
          Fecha para que te pague (opcional)
          <input type="date" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} />
        </label>
        <label>
          Nota (opcional)
          <input value={form.notes} onChange={(e) => set("notes", e.target.value)} maxLength={500} />
        </label>
      </div>
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          Registrar préstamo
        </button>
      </div>
    </form>
  );
}
