import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useMe } from "./auth/useAuth";
import Layout from "./components/Layout";
import AccountsPage from "./pages/AccountsPage";
import CategoriesPage from "./pages/CategoriesPage";
import DashboardPage from "./pages/DashboardPage";
import DebtsPage from "./pages/DebtsPage";
import GoalsPage from "./pages/GoalsPage";
import LoginPage from "./pages/LoginPage";
import ScenariosPage from "./pages/ScenariosPage";
import P2PPage from "./pages/P2PPage";
import RecurringPage from "./pages/RecurringPage";
import TransactionsPage from "./pages/TransactionsPage";

function RequireAuth() {
  const { data: user, isLoading } = useMe();
  const location = useLocation();
  if (isLoading) return <div className="center muted">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="movimientos" element={<TransactionsPage />} />
          <Route path="plataformas" element={<AccountsPage />} />
          <Route path="categorias" element={<CategoriesPage />} />
          <Route path="p2p" element={<P2PPage />} />
          <Route path="obligaciones" element={<RecurringPage />} />
          <Route path="deudas" element={<DebtsPage />} />
          <Route path="metas" element={<GoalsPage />} />
          <Route path="escenarios" element={<ScenariosPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
