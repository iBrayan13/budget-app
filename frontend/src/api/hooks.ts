import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  LoansSummary,
  Allocation,
  AccountKind,
  Plan,
  Scenario,
  DebtInput,
  DebtsSummary,
  Obligation,
  RecurringInput,
  RecurringSummary,
  AccountsSummary,
  Category,
  CategoryKind,
  ExchangeRate,
  ExpenseLevel,
  P2PSummary,
  Route,
  RouteInput,
  Transaction,
  TransactionInput,
  TransactionKind,
} from "./types";

export type Range = { start?: string; end?: string };

function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : "";
}

// Everything that changes money invalidates these, so balances and summaries stay in sync.
const MONEY_KEYS = [
  ["accounts"],
  ["transactions"],
  ["transfers"],
  ["routes"],
  ["p2p-summary"],
  ["recurring"],
  ["obligations"],
  ["debts"],
  ["plan"],
  ["allocations"],
  ["loans"],
];

function useInvalidate(keys: string[][] = MONEY_KEYS) {
  const qc = useQueryClient();
  return () => Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

// --- Accounts -------------------------------------------------------------------------------

export function useAccounts(includeInactive = false) {
  return useQuery({
    queryKey: ["accounts", includeInactive],
    queryFn: () => api<AccountsSummary>(`/accounts${qs({ include_inactive: includeInactive })}`),
  });
}

export type AccountInput = {
  name: string;
  kind: AccountKind;
  currency: string;
  initial_balance: string;
  notes: string | null;
};

export function useSaveAccount() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<AccountInput> & { id?: number; is_active?: boolean }) =>
      id
        ? api(`/accounts/${id}`, { method: "PATCH", json: body })
        : api("/accounts", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteAccount() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/accounts/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useSeedCategories() {
  const invalidate = useInvalidate([["categories"]]);
  return useMutation({
    mutationFn: () => api<{ categories: number }>("/setup/categories", { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useSeedDefaults() {
  const invalidate = useInvalidate([["accounts"], ["categories"]]);
  return useMutation({
    mutationFn: () => api<{ accounts: number; categories: number }>("/setup/defaults", { method: "POST" }),
    onSuccess: invalidate,
  });
}

// --- Categories -----------------------------------------------------------------------------

export function useCategories(includeInactive = false) {
  return useQuery({
    queryKey: ["categories", includeInactive],
    queryFn: () => api<Category[]>(`/categories${qs({ include_inactive: includeInactive })}`),
  });
}

export function useSaveCategory() {
  const invalidate = useInvalidate([["categories"]]);
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id?: number;
      name?: string;
      kind?: CategoryKind;
      level?: ExpenseLevel | null;
      is_active?: boolean;
    }) =>
      id
        ? api(`/categories/${id}`, { method: "PATCH", json: body })
        : api("/categories", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteCategory() {
  const invalidate = useInvalidate([["categories"]]);
  return useMutation({
    mutationFn: (id: number) => api(`/categories/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

// --- Exchange rates -------------------------------------------------------------------------

const RATE_DEPENDENT = [...MONEY_KEYS, ["rates"]];

export function useRates() {
  return useQuery({ queryKey: ["rates"], queryFn: () => api<ExchangeRate[]>("/exchange-rates") });
}

export function useSaveRate() {
  const invalidate = useInvalidate(RATE_DEPENDENT);
  return useMutation({
    mutationFn: (body: { currency: string; rate_date: string; rate: string }) =>
      api("/exchange-rates", { method: "PUT", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteRate() {
  const invalidate = useInvalidate(RATE_DEPENDENT);
  return useMutation({
    mutationFn: (id: number) => api(`/exchange-rates/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

// --- Transactions ---------------------------------------------------------------------------

export function useTransactions(filters: Range & { account_id?: number; kind?: TransactionKind }) {
  return useQuery({
    queryKey: ["transactions", filters],
    queryFn: () => api<Transaction[]>(`/transactions${qs(filters)}`),
  });
}

export function useSaveTransaction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: TransactionInput & { id?: number }) =>
      id
        ? api(`/transactions/${id}`, { method: "PUT", json: body })
        : api("/transactions", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteTransaction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/transactions/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

// --- P2P ------------------------------------------------------------------------------------

export function useRoutes(range: Range) {
  return useQuery({
    queryKey: ["routes", range],
    queryFn: () => api<Route[]>(`/transfer-routes${qs(range)}`),
  });
}

export function useSaveRoute() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: RouteInput & { id?: number }) =>
      id
        ? api<Route>(`/transfer-routes/${id}`, { method: "PUT", json: body })
        : api<Route>("/transfer-routes", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteRoute() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/transfer-routes/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useP2PSummary(range: Range) {
  return useQuery({
    queryKey: ["p2p-summary", range],
    queryFn: () => api<P2PSummary>(`/p2p/summary${qs(range)}`),
  });
}

// --- Fixed expenses & obligations ------------------------------------------------------------

export function useRecurring(includeInactive = false) {
  return useQuery({
    queryKey: ["recurring", includeInactive],
    queryFn: () => api<RecurringSummary>(`/recurring-expenses${qs({ include_inactive: includeInactive })}`),
  });
}

export function useSaveRecurring() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: RecurringInput & { id?: number }) =>
      id
        ? api(`/recurring-expenses/${id}`, { method: "PUT", json: body })
        : api("/recurring-expenses", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteRecurring() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/recurring-expenses/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useSchedulePreview(rrule: string, start_date: string, end_date: string | null) {
  return useQuery({
    queryKey: ["schedule-preview", rrule, start_date, end_date],
    queryFn: () =>
      api<{ rrule: string; dates: string[]; per_month: string }>("/recurring-expenses/preview", {
        method: "POST",
        json: { rrule, start_date, end_date, count: 4 },
      }),
    enabled: !!rrule && !!start_date,
    retry: false,
  });
}

export function useObligations(range: Range & { include_overdue?: boolean }) {
  return useQuery({
    queryKey: ["obligations", range],
    queryFn: () => api<Obligation[]>(`/obligations${qs(range)}`),
  });
}

export function usePayObligation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      account_id: number;
      amount?: string | null;
      occurred_on?: string;
      fx_rate?: string | null;
    }) => api<Obligation>(`/obligations/${id}/pay`, { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useObligationAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "skip" | "reopen" }) =>
      api<Obligation>(`/obligations/${id}/${action}`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

// --- Debts -----------------------------------------------------------------------------------

export function useDebts(includeInactive = false) {
  return useQuery({
    queryKey: ["debts", includeInactive],
    queryFn: () => api<DebtsSummary>(`/debts${qs({ include_inactive: includeInactive })}`),
  });
}

export function useSaveDebt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: DebtInput & { id?: number }) =>
      id ? api(`/debts/${id}`, { method: "PUT", json: body }) : api("/debts", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteDebt() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/debts/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useDebtPayment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      account_id: number;
      amount: string;
      amount_in: string | null;
      occurred_on: string;
    }) => api(`/debts/${id}/payments`, { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

// --- Phase 4: plan, goals, scenarios ---------------------------------------------------------

export function usePlan(month: string) {
  return useQuery({
    queryKey: ["plan", month],
    queryFn: () => api<Plan>(`/plan${qs({ month })}`),
  });
}

export function useSavePlanSettings() {
  const invalidate = useInvalidate([["plan"]]);
  return useMutation({
    mutationFn: (body: { emergency_fund_months: number }) =>
      api("/plan/settings", { method: "PATCH", json: body }),
    onSuccess: invalidate,
  });
}

export type GoalInput = {
  name: string;
  target_amount: string;
  target_date: string | null;
  priority: number;
  notes: string | null;
  is_active: boolean;
};

export function useSaveGoal() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: GoalInput & { id?: number }) =>
      id
        ? api(`/goals/${id}`, { method: "PUT", json: body })
        : api("/goals", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteGoal() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/goals/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useAllocations(goalId: number | null) {
  return useQuery({
    queryKey: ["allocations", goalId],
    queryFn: () => api<Allocation[]>(`/goals/${goalId}/allocations`),
    enabled: goalId !== null,
  });
}

export function useAllocate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({
      goalId,
      ...body
    }: {
      goalId: number;
      account_id: number;
      amount: string;
      allocated_on: string;
      notes?: string | null;
    }) => api<Allocation>(`/goals/${goalId}/allocations`, { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteAllocation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/goal-allocations/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useScenario(month: string, lifestyleTarget: string) {
  return useQuery({
    queryKey: ["scenario", month, lifestyleTarget],
    queryFn: () =>
      api<Scenario>(`/plan/scenario${qs({ month })}`, {
        method: "POST",
        json: { lifestyle_target: lifestyleTarget },
      }),
    enabled: lifestyleTarget !== "",
  });
}

// --- Loans ----------------------------------------------------------------------------------

export function useLoans() {
  return useQuery({ queryKey: ["loans"], queryFn: () => api<LoansSummary>("/loans") });
}

export function useSaveLoan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: {
      borrower: string;
      account_id: number;
      amount: string;
      start_date: string;
      due_date: string | null;
      notes: string | null;
    }) => api("/loans", { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteLoan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/loans/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useLoanPayment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({
      loanId,
      ...body
    }: {
      loanId: number;
      account_id: number;
      amount: string;
      occurred_on: string;
      notes?: string | null;
    }) => api(`/loans/${loanId}/payments`, { method: "POST", json: body }),
    onSuccess: invalidate,
  });
}

export function useDeleteLoanPayment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/loan-payments/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}
