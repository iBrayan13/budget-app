import { FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useLogin, useMe } from "../auth/useAuth";

export default function LoginPage() {
  const { data: user } = useMe();
  const login = useLogin();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (user) return <Navigate to={from} replace />;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    login.mutate({ email, password });
  }

  return (
    <div className="center">
      <form className="card login" onSubmit={onSubmit}>
        <h1>💰 Mi presupuesto</h1>
        <p className="muted">¡Qué bueno verte! Entra para ver tu plata en orden.</p>
        <label>
          Correo
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {login.isError && <p className="error">{login.error.message}</p>}
        <button className="btn" type="submit" disabled={login.isPending}>
          {login.isPending ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
