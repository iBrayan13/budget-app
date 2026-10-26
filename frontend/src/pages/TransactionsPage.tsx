import { FormEvent, useMemo, useState } from "react";
import {
  useAccounts,
  useCategories,
  useDeleteTransaction,
  useSaveTransaction,
  useTransactions,
} from "../api/hooks";
import type { Category, Transaction, TransactionInput, TransactionKind } from "../api/types";
import { useMe } from "../auth/useAuth";
import { confirmDelete, Empty, ErrorText, MonthPicker, Tile } from "../components/ui";
import { currentMonth, fmtMoney, monthRange, plain, today } from "../lib/format";

const KIND_LABEL: Record<TransactionKind, string> = {
  expense: "Gasto",
  income: "Ingreso",
  adjustment: "Ajuste",
};

export default function TransactionsPage() {
  const { data: user } = useMe();
  const base = user?.base_currency ?? "USD";
  const [month, setMonth] = useState(currentMonth());
  const [accountFilter, setAccountFilter] = useState<number | undefined>();
  const [editing, setEditing] = useState<Transaction | null>(null);

  const range = monthRange(month);
  const { data: txs, isLoading } = useTransactions({ ...range, account_id: accountFilter });
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories(true);
  const remove = useDeleteTransaction();

  const accountName = (id: number) => accounts?.accounts.find((a) => a.id === id)?.name ?? `#${id}`;
  const categoryById = useMemo(() => new Map((categories ?? []).map((c) => [c.id, c])), [categories]);

  const totals = useMemo(() => {
    const t = { income: 0, essential: 0, lifestyle: 0, missing: 0 };
    for (const tx of txs ?? []) {
      if (tx.amount_base === null) {
        if (tx.kind !== "adjustment") t.missing++;
        continue;
      }
      const v = Number(tx.amount_base);
      if (tx.kind === "income") t.income += v;
      if (tx.kind === "expense") {
        const level = tx.category_id ? categoryById.get(tx.category_id)?.level : null;
        if (level === "essential") t.essential += v;
        else t.lifestyle += v;
      }
    }
    return t;
  }, [txs, categoryById]);

  return (
    <>
      <header className="page-header">
        <h1>Movimientos</h1>
        <div className="row gap-sm">
          <select
            aria-label="Plataforma"
            value={accountFilter ?? ""}
            onChange={(e) => setAccountFilter(e.target.value ? Number(e.target.value) : undefined)}
          >
            <option value="">Todas las plataformas</option>
            {accounts?.accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <MonthPicker value={month} onChange={setMonth} />
        </div>
      </header>

      <section className="tiles">
        <Tile label="Ingresos del mes" value={fmtMoney(totals.income, base)} />
        <Tile label="Gastos esenciales" value={fmtMoney(totals.essential, base)} />
        <Tile label="Gastos estilo de vida" value={fmtMoney(totals.lifestyle, base)} />
        <Tile
          label="Total gastos"
          value={fmtMoney(totals.essential + totals.lifestyle, base)}
          hint={totals.missing ? `${totals.missing} sin tasa, no sumados` : undefined}
        />
      </section>

      <TransactionForm
        key={editing?.id ?? "new"}
        editing={editing}
        onDone={() => setEditing(null)}
        categories={categories ?? []}
      />

      {isLoading ? (
        <p className="muted">Cargando…</p>
      ) : !txs?.length ? (
        <Empty>No hay movimientos en este mes.</Empty>
      ) : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Plataforma</th>
                <th>Categoría</th>
                <th>Descripción</th>
                <th className="num">Monto</th>
                <th className="num">{base}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {txs.map((t) => {
                const cat = t.category_id ? categoryById.get(t.category_id) : undefined;
                return (
                  <tr key={t.id}>
                    <td>{t.occurred_on}</td>
                    <td>
                      <span className={`badge kind-${t.kind}`}>{KIND_LABEL[t.kind]}</span>
                    </td>
                    <td>{accountName(t.account_id)}</td>
                    <td>
                      {cat?.name ?? "—"}
                      {cat?.level === "essential" && <span className="muted small"> · esencial</span>}
                    </td>
                    <td className="muted">{t.description}</td>
                    <td className="num">
                      {t.kind === "expense" ? "−" : ""}
                      {fmtMoney(t.amount, t.currency)}
                    </td>
                    <td className="num muted">{fmtMoney(t.amount_base, base)}</td>
                    <td className="num nowrap">
                      <button className="link" onClick={() => setEditing(t)}>
                        Editar
                      </button>{" "}
                      <button
                        className="link danger"
                        onClick={() => confirmDelete("este movimiento") && remove.mutate(t.id)}
                      >
                        Borrar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function blank(kind: TransactionKind = "expense"): TransactionInput {
  return {
    account_id: 0,
    kind,
    amount: "",
    occurred_on: today(),
    category_id: null,
    description: null,
    fx_rate: null,
  };
}

function TransactionForm({
  editing,
  onDone,
  categories,
}: {
  editing: Transaction | null;
  onDone: () => void;
  categories: Category[];
}) {
  const { data: user } = useMe();
  const { data: accounts } = useAccounts();
  const save = useSaveTransaction();
  const [form, setForm] = useState<TransactionInput>(() =>
    editing
      ? {
          account_id: editing.account_id,
          kind: editing.kind,
          amount: plain(editing.amount),
          occurred_on: editing.occurred_on,
          category_id: editing.category_id,
          description: editing.description,
          fx_rate: editing.fx_rate ? plain(editing.fx_rate) : null,
        }
      : blank(),
  );
  const set = <K extends keyof TransactionInput>(k: K, v: TransactionInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const accountId = form.account_id || accounts?.accounts[0]?.id || 0;
  const account = accounts?.accounts.find((a) => a.id === accountId);
  const usable = categories.filter(
    (c) => (c.is_active || c.id === form.category_id) && c.kind === (form.kind === "income" ? "income" : "expense"),
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = {
      ...form,
      account_id: accountId,
      category_id: form.kind === "adjustment" ? null : form.category_id,
      fx_rate: form.fx_rate || null,
      description: form.description || null,
    };
    save.mutate(editing ? { ...body, id: editing.id } : body, {
      onSuccess: () => {
        setForm((f) => ({ ...blank(f.kind), account_id: f.account_id, occurred_on: f.occurred_on }));
        onDone();
      },
    });
  }

  if (accounts && accounts.accounts.length === 0) {
    return <Empty>Crea al menos una plataforma para registrar movimientos.</Empty>;
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <div className="row-between">
        <h2>{editing ? "Editar movimiento" : "Nuevo movimiento"}</h2>
        <div className="tabs" role="tablist">
          {(Object.keys(KIND_LABEL) as TransactionKind[]).map((k) => (
            <button
              type="button"
              key={k}
              role="tab"
              aria-selected={form.kind === k}
              className={form.kind === k ? "tab active" : "tab"}
              onClick={() => setForm((f) => ({ ...f, kind: k, category_id: null }))}
            >
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      </div>
      <div className="grid-4">
        <label>
          Plataforma
          <select value={accountId} onChange={(e) => set("account_id", Number(e.target.value))}>
            {accounts?.accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </select>
        </label>
        <label>
          Monto {account && <span className="muted">({account.currency})</span>}
          <input
            type="number"
            step="any"
            min={form.kind === "adjustment" ? undefined : "0"}
            value={form.amount}
            onChange={(e) => set("amount", e.target.value)}
            required
          />
        </label>
        {form.kind !== "adjustment" && (
          <label>
            Categoría
            <select
              value={form.category_id ?? ""}
              onChange={(e) => set("category_id", e.target.value ? Number(e.target.value) : null)}
              required={form.kind === "expense"}
            >
              <option value="">{form.kind === "expense" ? "Elige…" : "Sin categoría"}</option>
              {form.kind === "expense" ? (
                <>
                  <optgroup label="Esenciales (sobrevivir)">
                    {usable
                      .filter((c) => c.level === "essential")
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="Estilo de vida">
                    {usable
                      .filter((c) => c.level === "lifestyle")
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </optgroup>
                </>
              ) : (
                usable.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))
              )}
            </select>
          </label>
        )}
        <label>
          Fecha
          <input type="date" value={form.occurred_on} onChange={(e) => set("occurred_on", e.target.value)} required />
        </label>
      </div>
      <div className="grid-4">
        <label className="span-3">
          Descripción
          <input
            value={form.description ?? ""}
            onChange={(e) => set("description", e.target.value)}
            maxLength={500}
            placeholder={form.kind === "adjustment" ? "Ej. cuadre con saldo real (puede ser negativo)" : ""}
          />
        </label>
        {account && account.currency !== user?.base_currency && (
          <label>
            Tasa (opcional)
            <input
              type="number"
              step="any"
              min="0"
              value={form.fx_rate ?? ""}
              onChange={(e) => set("fx_rate", e.target.value || null)}
              placeholder={`${account.currency} por 1 ${user?.base_currency}`}
            />
          </label>
        )}
      </div>
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          {editing ? "Guardar" : "Registrar"}
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
