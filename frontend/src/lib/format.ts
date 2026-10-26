const FIAT_DECIMALS: Record<string, number> = { COP: 0, VES: 2, USD: 2 };

/** Formats a decimal string. Crypto keeps more decimals, COP none. */
export function fmtMoney(value: string | number | null | undefined, currency?: string): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  const decimals = currency ? (FIAT_DECIMALS[currency] ?? (currency.startsWith("USD") ? 2 : 4)) : 2;
  const text = n.toLocaleString("es-CO", {
    minimumFractionDigits: Math.min(decimals, 2),
    maximumFractionDigits: decimals,
  });
  return currency ? `${text} ${currency}` : text;
}

export function fmtPct(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toLocaleString("es-CO", { maximumFractionDigits: 2 })} %`;
}

/** Strips trailing zeros of a NUMERIC(20,8) string, for form inputs. */
export function plain(value: string | null | undefined): string {
  if (!value) return "";
  return value.includes(".") ? value.replace(/\.?0+$/, "") : value;
}

export function today(): string {
  const d = new Date();
  return toISODate(d);
}

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function currentMonth(): string {
  return today().slice(0, 7);
}

/** "2026-10" -> { start: "2026-10-01", end: "2026-10-31" } */
export function monthRange(month: string): { start: string; end: string } {
  const [y, m] = month.split("-").map(Number);
  return { start: `${month}-01`, end: toISODate(new Date(y, m, 0)) };
}

export const ACCOUNT_KIND_LABEL: Record<string, string> = {
  bank: "Banco",
  exchange: "Exchange",
  wallet: "Billetera",
  cash: "Efectivo",
  credit_card: "Tarjeta de crédito",
  other: "Otra",
};

/** Monedas que usas (plataformas, tasas, deudas, gastos fijos). */
export const CURRENCIES = ["USD", "USDT", "USDC", "COP", "VES", "EUR"];
