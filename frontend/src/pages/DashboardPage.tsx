import { useState } from "react";
import { Link } from "react-router-dom";
import { useAccounts, useDebts, useLoans, usePlan, useRecurring, useSeedDefaults } from "../api/hooks";
import { useMe } from "../auth/useAuth";
import { RuleBars } from "../components/RuleBars";
import { ErrorText, MonthPicker, Progress, Tile } from "../components/ui";
import { currentMonth, fmtMoney, fmtPct } from "../lib/format";

export default function DashboardPage() {
  const { data: user } = useMe();
  const [month, setMonth] = useState(currentMonth());
  const { data: plan } = usePlan(`${month}-01`);
  const { data: accounts } = useAccounts();
  const { data: recurring } = useRecurring();
  const { data: debts } = useDebts();
  const { data: loans } = useLoans();
  const seed = useSeedDefaults();
  const base = user?.base_currency ?? "USD";
  const m = (v: string | null | undefined) => fmtMoney(v, base);

  const fund = plan?.goals.find((g) => g.kind === "emergency_fund");
  const liveLifestyle = plan ? Number(plan.live) - Number(plan.survive) : 0;

  return (
    <>
      <header className="page-header">
        <div>
          <h1>¡Hola{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}! 👋</h1>
          <span className="muted">Así va tu plata este mes</span>
        </div>
        <MonthPicker value={month} onChange={setMonth} />
      </header>

      {accounts && accounts.accounts.length === 0 && (
        <div className="card form onboarding">
          <h2>Empecemos</h2>
          <p>
            Carga las plataformas sugeridas (Facebank USD, Binance USDT, Zinli USD, El Dorado USDT, Nequi COP,
            Efectivo COP) y las categorías. Luego puedes editarlas.
          </p>
          <div className="row gap-sm">
            <button className="btn" onClick={() => seed.mutate()} disabled={seed.isPending}>
              Cargar sugeridas
            </button>
            <Link className="btn-ghost" to="/plataformas">
              Crear las mías
            </Link>
          </div>
          <ErrorText error={seed.error} />
        </div>
      )}

      <h2>Este mes</h2>
      <section className="tiles">
        <Tile label="Ingreso bruto" value={m(plan?.income_month)} />
        <Tile
          label="Neto después de gastos"
          value={<span className={Number(plan?.net_month ?? 0) < 0 ? "negative" : ""}>{m(plan?.net_month)}</span>}
          hint={plan ? `gastos ${m(plan.costs_month)}` : undefined}
        />
        <Tile label="Comisiones P2P" value={m(plan?.p2p_month)} />
        <Tile label="Disponible total" value={m(plan?.accounts_total)} hint={`${accounts?.accounts.length ?? 0} plataformas`} />
        <Tile label="Disponible libre" value={m(plan?.free)} hint={plan ? `${m(plan.reserved)} apartado en metas` : undefined} />
        <Tile label="Te deben" value={m(loans?.total_balance_base)} hint="préstamos por cobrar" />
      </section>

      <h2>Promedio de los últimos 3 meses</h2>
      <section className="tiles">
        <Tile label="Costo de sobrevivir" value={m(plan?.survive)} hint="esenciales, fijos y variables, más P2P" />
        <Tile
          label="Costo de vivir bien"
          value={m(plan?.live)}
          hint={plan ? `sobrevivir + ${m(String(liveLifestyle))} de estilo de vida` : undefined}
        />
        <Tile label="Ingreso promedio" value={m(plan?.income_avg)} />
        <Tile
          label="Puedes ahorrar al mes"
          value={<span className={Number(plan?.savings_capacity ?? 0) < 0 ? "negative" : ""}>{m(plan?.savings_capacity)}</span>}
          hint="ingreso − vivir bien"
        />
      </section>

      <h2>Fondo de emergencia</h2>
      <section className="tiles">
        <Tile
          label="Tienes"
          value={m(fund?.current)}
          hint={plan?.fund_target ? `de ${m(plan.fund_target)} (${plan.emergency_months} meses)` : "aún sin costo de sobrevivir"}
        />
        <Tile
          label="Cubre"
          value={plan?.fund_months_covered ? `${Number(plan.fund_months_covered).toFixed(1)} meses` : "—"}
        />
        <Tile
          label="Te falta"
          value={m(plan?.fund_missing)}
          hint={plan?.fund_eta ? `llegas el ${plan.fund_eta}` : "sin ritmo de ahorro"}
        />
        <div className="card tile">
          <span className="muted small">Avance</span>
          <Progress pct={fund?.progress_pct ?? null} />
        </div>
      </section>

      {plan && <RuleBars plan={plan} />}

      <h2>Compromisos</h2>
      <section className="tiles">
        <Tile
          label="Gastos fijos al mes"
          value={m(recurring?.monthly_total_base)}
          hint={recurring ? `esenciales ${m(recurring.monthly_essential_base)}` : undefined}
        />
        <Tile
          label="Deuda total"
          value={m(debts?.total_balance_base)}
          hint={debts?.debt_ratio_pct ? `endeudamiento ${fmtPct(debts.debt_ratio_pct)}` : undefined}
        />
      </section>

      {accounts && accounts.accounts.length > 0 && (
        <div className="card table-wrap">
          <h2>Saldo por plataforma</h2>
          <table className="table">
            <tbody>
              {accounts.accounts.map((a) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td className="num">{fmtMoney(a.balance, a.currency)}</td>
                  <td className="num muted">{a.currency === base ? "" : m(a.balance_base)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
