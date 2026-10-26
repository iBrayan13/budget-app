import { FormEvent, useState } from "react";
import {
  useAccounts,
  useAllocate,
  useAllocations,
  useDeleteAllocation,
  useDeleteGoal,
  usePlan,
  useSaveGoal,
  useSavePlanSettings,
  type GoalInput,
} from "../api/hooks";
import type { Allocation, Goal } from "../api/types";
import { confirmDelete, Empty, ErrorText, MonthPicker, Progress, Tile } from "../components/ui";
import { useMe } from "../auth/useAuth";
import { currentMonth, fmtMoney, plain, today } from "../lib/format";

export default function GoalsPage() {
  const { data: user } = useMe();
  const base = user?.base_currency ?? "USD";
  const [month, setMonth] = useState(currentMonth());
  const { data: plan, isLoading } = usePlan(`${month}-01`);
  const savePlanSettings = useSavePlanSettings();
  const [editing, setEditing] = useState<Goal | null>(null);
  const m = (v: string | null | undefined) => fmtMoney(v, base);

  if (isLoading || !plan) return <p className="muted">Cargando…</p>;
  const fund = plan.goals.find((g) => g.kind === "emergency_fund");
  const savings = plan.goals.filter((g) => g.kind === "savings");

  return (
    <>
      <header className="page-header">
        <h1>Fondo de emergencia y metas</h1>
        <MonthPicker value={month} onChange={setMonth} />
      </header>

      <section className="tiles">
        <Tile label="Disponible libre" value={m(plan.free)} hint={`${m(plan.reserved)} apartado`} />
        <Tile label="Aportas al mes (promedio)" value={m(plan.pace)} hint="a fondo y metas" />
      </section>

      {fund && (
        <div className="card goal-card">
          <div className="row-between">
            <h2>{fund.name}</h2>
            <label className="row gap-sm small">
              Meses que cubre
              <select
                value={plan.emergency_months}
                onChange={(e) => savePlanSettings.mutate({ emergency_fund_months: Number(e.target.value) })}
              >
                {Array.from({ length: 24 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Progress pct={fund.progress_pct} />
          <div className="facts">
            <span>
              Tienes <strong>{m(fund.current)}</strong>
            </span>
            <span>
              Meta <strong>{m(fund.target_amount)}</strong>
            </span>
            <span>
              Te falta <strong>{m(fund.remaining)}</strong>
            </span>
            <span>
              Cubre <strong>{plan.fund_months_covered ? `${Number(plan.fund_months_covered).toFixed(1)} meses` : "—"}</strong>
            </span>
            <span>
              Ritmo <strong>{m(fund.pace)}/mes</strong>
            </span>
            {fund.eta && (
              <span>
                Llegas el <strong>{fund.eta}</strong>
              </span>
            )}
          </div>
          <p className="muted small">
            Es {plan.emergency_months} meses de lo que cuesta sobrevivir ({m(plan.survive)} al mes). Lo ajustas con el
            menú de arriba.
          </p>
          <GoalActions goal={fund} base={base} />
        </div>
      )}

      <h2>Metas de ahorro</h2>
      {savings.length === 0 ? (
        <Empty>Aún no tienes metas. Crea una para la PC, el carro, la moto, la casa o lo que quieras.</Empty>
      ) : (
        <div className="stack">
          {savings.map((g) => (
            <div key={g.id} className={`card goal-card ${g.is_active ? "" : "archived"}`}>
              <div className="row-between">
                <div>
                  <strong>{g.name}</strong>
                  {g.target_date && <span className="muted small"> · hasta {g.target_date}</span>}
                </div>
                <span>
                  {m(g.current)} de {m(g.target_amount)}
                </span>
              </div>
              <Progress pct={g.progress_pct} />
              <div className="facts">
                <span>
                  Falta <strong>{m(g.remaining)}</strong>
                </span>
                {g.monthly_needed && (
                  <span>
                    Necesitas <strong>{m(g.monthly_needed)}/mes</strong> para la fecha
                  </span>
                )}
                <span>
                  Ritmo <strong>{m(g.pace)}/mes</strong>
                </span>
                {g.eta && (
                  <span>
                    Llegas el <strong>{g.eta}</strong>
                  </span>
                )}
              </div>
              <GoalActions
                goal={g}
                base={base}
                onEdit={() => setEditing(g)}
              />
            </div>
          ))}
        </div>
      )}

      <GoalForm key={editing?.id ?? "new"} editing={editing} onDone={() => setEditing(null)} />
    </>
  );
}

/** Aportar, ver aportes y (solo metas) editar/borrar. */
function GoalActions({ goal, base, onEdit }: { goal: Goal; base: string; onEdit?: () => void }) {
  const [open, setOpen] = useState<"none" | "allocate" | "list">("none");
  const remove = useDeleteGoal();
  const isEmergency = goal.kind === "emergency_fund";

  return (
    <>
      <div className="row gap-sm">
        <button className="btn-ghost small" onClick={() => setOpen(open === "allocate" ? "none" : "allocate")}>
          Aportar
        </button>
        <button className="btn-ghost small" onClick={() => setOpen(open === "list" ? "none" : "list")}>
          Ver aportes
        </button>
        {!isEmergency && onEdit && (
          <button className="btn-ghost small" onClick={onEdit}>
            Editar
          </button>
        )}
        {!isEmergency && (
          <button
            className="btn-ghost small danger"
            onClick={() => confirmDelete(`la meta ${goal.name} (el dinero vuelve a libre)`) && remove.mutate(goal.id)}
          >
            Borrar
          </button>
        )}
      </div>
      <ErrorText error={remove.error} />
      {open === "allocate" && <AllocateForm goalId={goal.id} onDone={() => setOpen("list")} />}
      {open === "list" && <AllocationList goalId={goal.id} base={base} />}
    </>
  );
}

function AllocateForm({ goalId, onDone }: { goalId: number; onDone: () => void }) {
  const { data } = useAccounts();
  const allocate = useAllocate();
  const accounts = data?.accounts ?? [];
  const [accountId, setAccountId] = useState<number | null>(null);
  const account = accounts.find((a) => a.id === (accountId ?? accounts[0]?.id));
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!account) return;
    allocate.mutate(
      { goalId, account_id: account.id, amount, allocated_on: date },
      { onSuccess: () => { setAmount(""); onDone(); } },
    );
  }

  if (accounts.length === 0) return <Empty>Primero crea una plataforma para apartar dinero.</Empty>;

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
        Monto {account && `(${account.currency})`}
        <input
          type="number"
          step="any"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
          placeholder="negativo para liberar"
        />
      </label>
      <label>
        Fecha
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <div className="row gap-sm">
        <button className="btn" disabled={allocate.isPending}>
          Apartar
        </button>
      </div>
      <p className="muted small span-3">
        El dinero se queda en {account?.name ?? "la plataforma"}, pero queda apartado para esta meta y deja de contar
        como libre.
      </p>
      <ErrorText error={allocate.error} />
    </form>
  );
}

function AllocationList({ goalId, base }: { goalId: number; base: string }) {
  const { data, isLoading } = useAllocations(goalId);
  const remove = useDeleteAllocation();
  if (isLoading) return <p className="muted small">Cargando aportes…</p>;
  if (!data?.length) return <p className="muted small">Sin aportes todavía.</p>;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Plataforma</th>
            <th className="num">Monto</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data.map((a: Allocation) => (
            <tr key={a.id}>
              <td>{a.allocated_on}</td>
              <td>{a.account_name}</td>
              <td className="num">
                {fmtMoney(a.amount, a.currency)}
                {a.amount.startsWith("-") ? " (liberado)" : ""}
              </td>
              <td className="num">
                <button
                  className="link danger"
                  onClick={() => confirmDelete("este aporte") && remove.mutate(a.id)}
                >
                  Quitar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ErrorText error={remove.error} />
      <span className="muted small">Base: {base}. Los montos están en la moneda de cada plataforma.</span>
    </div>
  );
}

function blank(): GoalInput {
  return { name: "", target_amount: "", target_date: null, priority: 0, notes: null, is_active: true };
}

function GoalForm({ editing, onDone }: { editing: Goal | null; onDone: () => void }) {
  const save = useSaveGoal();
  const [form, setForm] = useState<GoalInput>(() =>
    editing
      ? {
          name: editing.name,
          target_amount: plain(editing.target_amount),
          target_date: editing.target_date,
          priority: editing.priority,
          notes: editing.notes,
          is_active: editing.is_active,
        }
      : blank(),
  );
  const set = <K extends keyof GoalInput>(k: K, v: GoalInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = { ...form, target_date: form.target_date || null, notes: form.notes || null };
    save.mutate(editing ? { ...body, id: editing.id } : body, {
      onSuccess: () => {
        setForm(blank());
        onDone();
      },
    });
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h2>{editing ? `Editar ${editing.name}` : "Nueva meta de ahorro"}</h2>
      <div className="grid-4">
        <label>
          Nombre
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={120} placeholder="PC, carro, moto…" />
        </label>
        <label>
          Monto objetivo
          <input
            type="number"
            step="any"
            min="0"
            value={form.target_amount}
            onChange={(e) => set("target_amount", e.target.value)}
            required
          />
        </label>
        <label>
          Fecha objetivo (opcional)
          <input type="date" value={form.target_date ?? ""} onChange={(e) => set("target_date", e.target.value || null)} />
        </label>
        <label>
          Prioridad
          <select value={form.priority} onChange={(e) => set("priority", Number(e.target.value))}>
            {[0, 1, 2, 3].map((p) => (
              <option key={p} value={p}>
                {["Normal", "Alta", "Muy alta", "Urgente"][p]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorText error={save.error} />
      <div className="row gap-sm">
        <button className="btn" disabled={save.isPending}>
          {editing ? "Guardar" : "Crear meta"}
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

