import { NavLink, Outlet } from "react-router-dom";
import { useLogout, useMe } from "../auth/useAuth";

const NAV = [
  { to: "/", icon: "🏠", label: "Dashboard", end: true },
  { to: "/movimientos", icon: "💸", label: "Movimientos" },
  { to: "/plataformas", icon: "🏦", label: "Plataformas" },
  { to: "/p2p", icon: "🔄", label: "P2P" },
  { to: "/categorias", icon: "🏷️", label: "Categorías" },
  { to: "/obligaciones", icon: "📅", label: "Gastos fijos" },
  { to: "/deudas", icon: "💳", label: "Deudas" },
  { to: "/metas", icon: "🎯", label: "Metas y fondo" },
  { to: "/prestamos", icon: "🤝", label: "Préstamos" },
  { to: "/escenarios", icon: "🧭", label: "Escenarios" },
];

export default function Layout() {
  const { data: user } = useMe();
  const logout = useLogout();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">💰 Mi presupuesto</div>
        <nav>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="muted small">👋 {user?.full_name || user?.email}</span>
          <button className="btn-ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
