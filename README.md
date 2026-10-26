# Presupuesto Personal

Web app para medir ingresos, gastos fijos y variables, transferencias P2P entre plataformas
(Facebank, Binance, Zinli, El Dorado, Nequi…), deudas, metas de ahorro y fondo de emergencia.

**Stack:** FastAPI · SQLAlchemy 2 · Alembic · Pydantic Settings · PostgreSQL (servidor propio) · React 18 + Vite + TypeScript · TanStack Query.

## Arrancar en desarrollo

Requisitos: Docker Desktop y **tu propio servidor PostgreSQL**. Docker Compose no levanta
Postgres: el backend se conecta al servidor que indiques en `.env`.

1. Crea la base en tu servidor (una vez): `CREATE DATABASE budget;`
2. Configura `.env`:
   ```bash
   cp .env.example .env   # pon POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB y un SECRET_KEY
   ```
   `POSTGRES_HOST=localhost` sirve para tu PC. Dentro del contenedor el backend usa
   `host.docker.internal` para llegar a ese mismo servidor. Si tu Postgres está en otra máquina,
   pon `DOCKER_POSTGRES_HOST=ip-o-dominio`.
3. Arranca. Las migraciones de Alembic se aplican solas al iniciar el backend:
   ```bash
   docker compose up -d --build
   docker compose exec backend python -m app.cli create-user --email tu@correo.com --name "Tu nombre"
   ```

- App: http://localhost:5173
- API docs: http://localhost:8000/api/docs

No hay registro público: los usuarios se crean con el CLI. Para cambiar una contraseña:
`docker compose exec backend python -m app.cli set-password --email tu@correo.com`.

## Comandos útiles

```bash
# Tests: usan POSTGRES_TEST_DB (budget_test), que se crea sola si el usuario tiene CREATEDB.
# Nunca tocan tu base real.
docker compose exec backend python -m pytest

# Lint / formato
docker compose exec backend sh -c "ruff check . && ruff format --check ."

# Nueva migración después de cambiar modelos
docker compose exec backend alembic revision --autogenerate -m "descripcion"
docker compose exec backend alembic upgrade head

# Build del frontend (incluye chequeo de tipos)
docker compose exec frontend npm run build
```

## Conceptos del modelo

| Tabla | Para qué |
|---|---|
| `accounts` | Cada plataforma con su moneda (USD, USDT, COP…). Saldo = inicial + movimientos. |
| `categories` | Ingreso o gasto; los gastos son `essential` (sobrevivir) o `lifestyle` (vivir bien). |
| `recurring_expenses` → `obligations` | Gastos fijos con regla RRULE (mensual, bimestral, 15 y 30, anual…) y sus fechas concretas. |
| `transactions` | Ingresos, gastos y ajustes en una cuenta. `fx_rate` = unidades de la moneda por 1 USD. |
| `transfers` / `transfer_routes` | Movimientos P2P. Costo real = salida/tasa_ref − entrada/tasa_ref (comisión + spread). |
| `exchange_rates` | Tasas de referencia manuales por fecha. |
| `debts` | Préstamo a cuotas, tarjeta (cuenta con saldo negativo) o deuda informal. |
| `savings_goals` / `goal_allocations` | Metas como sobres virtuales; el fondo de emergencia es una meta especial (6 × sobrevivir). |

## Roadmap

1. ✅ Base: Docker, API, auth con cookie httpOnly, esquema completo, shell de React.
2. ✅ Plataformas con saldos, tasas de referencia, categorías, movimientos y rutas P2P con costo real
   (comisión + spread). En el Dashboard, "Cargar sugeridas" crea plataformas y categorías iniciales.
3. ✅ Gastos fijos con cualquier frecuencia y su calendario de pagos (pagar, omitir, reabrir),
   deudas (préstamo a cuotas con amortización, tarjeta, informal), nivel y capacidad de endeudamiento.
4. ✅ Fondo de emergencia (meses configurables, ritmo y fecha estimada), metas de ahorro con aportes
   virtuales, Dashboard con todas las cifras, regla 50/30/20 y escenarios con el deslizador de gasto.
5. Producción: Caddy + HTTPS en VPS, límite de intentos de login, backups.
