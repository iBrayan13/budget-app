import { FormEvent, useState } from "react";
import {
  useAccounts,
  useDeleteAccount,
  useDeleteRate,
  useRates,
  useSaveAccount,
  useSaveRate,
  type AccountInput,
} from "../api/hooks";
import type { Account, AccountKind } from "../api/types";
import { confirmDelete, Empty, ErrorText } from "../components/ui";
import { ACCOUNT_KIND_LABEL, CURRENCIES, fmtMoney, plain, today } from "../lib/format";

const EMPTY: AccountInput = { name: "", kind: "wallet", currency: "USD", initial_balance: "0", notes: null };

export default function AccountsPage() {
  const [showArchived, setShowArchived] = useState(false);
  const { data, isLoading } = useAccounts(showArchived);
  const [editing, setEditing] = useState<Account | null>(null);
  const save = useSaveAccount();
  const remove = useDeleteAccount();

  return (
    <>
      <header className="page-header">
        <h1>Plataformas</h1>
        {data && (
          <span>
            Disponible total: <strong>{fmtMoney(data.total_base, data.base_currency)}</strong>
          </span>
        )}
      </header>

      {data && data.accounts_without_rate.length > 0 && (
        <p className="warning">
          Sin tasa de referencia, no se suman al total: {data.accounts_without_rate.join(", ")}. Agrega la tasa
          abajo.
        </p>
      )}

      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : data?.accounts.length === 0 ? (
        <Empty>Aún no tienes plataformas. Créalas aquí o carga las sugeridas desde el Dashboard.</Empty>
      ) : (
        <section className="tiles">
          {data?.accounts.map((a) => (
            <div key={a.id} className={`card tile ${a.is_active ? "" : "archived"}`}>
              <div className="row-between">
                <strong>{a.name}</strong>
                <span className="badge">{ACCOUNT_KIND_LABEL[a.kind]}</span>
              </div>
              <span className="tile-value">{fmtMoney(a.balance, a.currency)}</span>
              <span className="muted small">
                {a.currency === data.base_currency
                  ? " "
                  : a.balance_base !== null
                    ? `≈ ${fmtMoney(a.balance_base, data.base_currency)}`
                    : "sin tasa"}
              </span>
              <div className="row gap-sm">
                <button className="btn-ghost small" onClick={() => setEditing(a)}>
                  Editar
                </button>
                <button
                  className="btn-ghost small"
                  onClick={() => save.mutate({ id: a.id, is_active: !a.is_active })}
                >
                  {a.is_active ? "Archivar" : "Reactivar"}
                </button>
                <button
                  className="btn-ghost small danger"
                  onClick={() => confirmDelete(a.name) && remove.mutate(a.id)}
                >
                  Borrar
                </button>
              </div>
            </div>
          ))}
        </section>
      )}
      <ErrorText error={remove.error ?? save.error} />
      <label className="row gap-sm small muted toggle">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivadas
      </label>

      <div className="two-col">
        <AccountForm key={editing?.id ?? "new"} account={editing} onDone={() => setEditing(null)} />
        <RatesSection base={data?.base_currency ?? "USD"} />
      </div>
    </>
  );
}

function AccountForm({ account, onDone }: { account: Account | null; onDone: () => void }) {
  const [form, setForm] = useState<AccountInput>(
    account
      ? {
          name: account.name,
          kind: account.kind,
          currency: account.currency,
          initial_balance: plain(account.initial_balance) || "0",
          notes: account.notes,
        }
      : EMPTY,
  );
  const save = useSaveAccount();
  const set = <K extends keyof AccountInput>(k: K, v: AccountInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = account ? { id: account.id, ...form, currency: undefined } : form;
    save.mutate(body, {
      onSuccess: () => {
        setForm(EMPTY);
        onDone();
      },
    });
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h2>{account ? `Editar ${account.name}` : "Nueva plataforma"}</h2>
      <label>
        Nombre
        <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={80} />
      </label>
      <div className="grid-2">
        <label>
          Tipo
          <select value={form.kind} onChange={(e) => set("kind", e.target.value as AccountKind)}>
            {Object.entries(ACCOUNT_KIND_LABEL).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Moneda
          <select value={form.currency} onChange={(e) => set("currency", e.target.value)} disabled={!!account}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Saldo inicial
        <input
          type="number"
          step="any"
          value={form.initial_balance}
          onChange={(e) => set("initial_balance", e.target.value)}
          required
        />
        <span className="muted small">Lo que había en la plataforma antes de empezar a registrar.</span>
      </label>
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          {account ? "Guardar" : "Crear"}
        </button>
        {account && (
          <button type="button" className="btn-ghost" onClick={onDone}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

function RatesSection({ base }: { base: string }) {
  const { data: rates } = useRates();
  const save = useSaveRate();
  const remove = useDeleteRate();
  const [form, setForm] = useState({ currency: "COP", rate_date: today(), rate: "" });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate(form, { onSuccess: () => setForm((f) => ({ ...f, rate: "" })) });
  }

  return (
    <div className="card form">
      <h2>Tasas de referencia</h2>
      <p className="muted small">
        Cuántas unidades de la moneda equivalen a 1 {base} (ej. TRM). Se usan para valorar saldos y medir el costo
        real del P2P. USDT/USDC se toman 1:1 si no registras tasa.
      </p>
      <form className="grid-3" onSubmit={onSubmit}>
        <select aria-label="Moneda" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          aria-label="Fecha"
          type="date"
          value={form.rate_date}
          onChange={(e) => setForm({ ...form, rate_date: e.target.value })}
          required
        />
        <input
          aria-label="Tasa"
          type="number"
          step="any"
          min="0"
          placeholder={`por 1 ${base}`}
          value={form.rate}
          onChange={(e) => setForm({ ...form, rate: e.target.value })}
          required
        />
        <button className="btn" disabled={save.isPending}>
          Guardar tasa
        </button>
      </form>
      <ErrorText error={save.error ?? remove.error} />
      {rates && rates.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Moneda</th>
              <th className="num">1 {base} =</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rates.slice(0, 15).map((r) => (
              <tr key={r.id}>
                <td>{r.rate_date}</td>
                <td>{r.currency}</td>
                <td className="num">{fmtMoney(r.rate, r.currency)}</td>
                <td className="num">
                  <button className="link danger" onClick={() => remove.mutate(r.id)}>
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
