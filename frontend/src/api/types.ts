// Decimals travel as strings to keep exact precision.
export type Dec = string;

export type AccountKind = "bank" | "exchange" | "wallet" | "cash" | "credit_card" | "other";

export type Account = {
  id: number;
  name: string;
  kind: AccountKind;
  currency: string;
  initial_balance: Dec;
  is_active: boolean;
  notes: string | null;
  balance: Dec;
  rate: Dec | null;
  balance_base: Dec | null;
};

export type AccountsSummary = {
  base_currency: string;
  total_base: Dec;
  accounts_without_rate: string[];
  accounts: Account[];
};

export type CategoryKind = "income" | "expense";
export type ExpenseLevel = "essential" | "lifestyle";

export type Category = {
  id: number;
  name: string;
  kind: CategoryKind;
  level: ExpenseLevel | null;
  color: string | null;
  is_active: boolean;
};

export type ExchangeRate = { id: number; currency: string; rate_date: string; rate: Dec };

export type TransactionKind = "income" | "expense" | "adjustment";

export type Transaction = {
  id: number;
  account_id: number;
  kind: TransactionKind;
  amount: Dec;
  currency: string;
  occurred_on: string;
  category_id: number | null;
  description: string | null;
  fx_rate: Dec | null;
  amount_base: Dec | null;
};

export type TransactionInput = Omit<Transaction, "id" | "currency" | "amount_base">;

export type Cost = {
  value_out: Dec | null;
  value_in: Dec | null;
  cost: Dec | null;
  fee: Dec | null;
  spread: Dec | null;
  cost_pct: Dec | null;
};

export type Transfer = {
  id: number;
  route_id: number | null;
  step: number | null;
  from_account_id: number;
  to_account_id: number;
  from_currency: string;
  to_currency: string;
  amount_out: Dec;
  amount_in: Dec;
  fee_amount: Dec;
  ref_rate_out: Dec | null;
  ref_rate_in: Dec | null;
  occurred_on: string;
  notes: string | null;
  cost: Cost;
};

export type TransferStepInput = {
  from_account_id: number;
  to_account_id: number;
  amount_out: string;
  amount_in: string;
  fee_amount: string;
  ref_rate_out: string | null;
  ref_rate_in: string | null;
  occurred_on: string | null;
  notes: string | null;
};

export type Route = {
  id: number;
  name: string | null;
  started_on: string;
  notes: string | null;
  steps: Transfer[];
  cost: Cost;
};

export type RouteInput = {
  name: string | null;
  started_on: string;
  notes: string | null;
  steps: TransferStepInput[];
};

export type P2PSummary = {
  base_currency: string;
  count: number;
  volume: Dec;
  cost: Dec;
  fees: Dec;
  spread: Dec;
  cost_pct: Dec | null;
  missing_rates: number;
  by_pair: {
    from_account_id: number;
    to_account_id: number;
    count: number;
    volume: Dec;
    cost: Dec;
    cost_pct: Dec | null;
  }[];
};

// --- Phase 3: fixed expenses, obligations, debts --------------------------------------------

export type RecurringExpense = {
  id: number;
  name: string;
  category_id: number;
  level: ExpenseLevel | null;
  account_id: number | null;
  amount: Dec;
  currency: string;
  rrule: string;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  notes: string | null;
  debt_id: number | null;
  per_month: Dec;
  monthly_amount: Dec;
  monthly_amount_base: Dec | null;
  next_due_date: string | null;
};

export type RecurringInput = {
  name: string;
  category_id: number;
  account_id: number | null;
  amount: string;
  currency: string;
  rrule: string;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  notes: string | null;
};

export type RecurringSummary = {
  base_currency: string;
  monthly_total_base: Dec;
  monthly_essential_base: Dec;
  monthly_lifestyle_base: Dec;
  without_rate: string[];
  items: RecurringExpense[];
};

export type ObligationStatus = "pending" | "paid" | "skipped";

export type Obligation = {
  id: number;
  recurring_expense_id: number;
  name: string;
  category_id: number;
  account_id: number | null;
  debt_id: number | null;
  due_date: string;
  expected_amount: Dec;
  currency: string;
  expected_base: Dec | null;
  status: ObligationStatus;
  is_overdue: boolean;
  transaction_id: number | null;
  paid_amount: Dec | null;
  paid_currency: string | null;
};

export type DebtKind = "installment_loan" | "credit_card" | "informal";

export type DebtSchedule = {
  installment_amount: string;
  rrule: string;
  first_due_date: string;
  installments_total: number | null;
  account_id: number | null;
};

export type DebtInput = {
  name: string;
  kind: DebtKind;
  creditor: string | null;
  currency: string;
  original_amount: string;
  interest_rate_annual: string | null;
  start_date: string;
  account_id: number | null;
  schedule: DebtSchedule | null;
  is_active: boolean;
  notes: string | null;
};

export type Debt = {
  id: number;
  name: string;
  kind: DebtKind;
  creditor: string | null;
  currency: string;
  original_amount: Dec;
  interest_rate_annual: Dec | null;
  installment_amount: Dec | null;
  installments_total: number | null;
  start_date: string;
  account_id: number | null;
  recurring_expense_id: number | null;
  schedule_rrule: string | null;
  schedule_first_due_date: string | null;
  schedule_account_id: number | null;
  is_active: boolean;
  notes: string | null;
  paid_total: Dec;
  payments_count: number;
  balance: Dec;
  balance_base: Dec | null;
  progress_pct: Dec;
  remaining_installments: number | null;
  monthly_payment: Dec | null;
  monthly_payment_base: Dec | null;
  total_interest: Dec | null;
  next_due_date: string | null;
  next_due_amount: Dec | null;
  end_date: string | null;
};

export type DebtsSummary = {
  base_currency: string;
  total_balance_base: Dec;
  monthly_payments_base: Dec;
  avg_monthly_income_base: Dec | null;
  debt_ratio_pct: Dec | null;
  max_ratio_pct: Dec;
  capacity_base: Dec | null;
  items: Debt[];
};

// --- Phase 4: plan, goals, scenarios --------------------------------------------------------

export type GoalKind = "savings" | "emergency_fund";

export type Goal = {
  id: number;
  name: string;
  kind: GoalKind;
  target_amount: Dec | null;
  target_date: string | null;
  priority: number;
  is_active: boolean;
  notes: string | null;
  current: Dec;
  progress_pct: Dec | null;
  remaining: Dec | null;
  monthly_needed: Dec | null;
  pace: Dec;
  eta: string | null;
};

export type Plan = {
  month: string;
  base_currency: string;
  income_month: Dec;
  costs_month: Dec;
  p2p_month: Dec;
  net_month: Dec;
  income_avg: Dec;
  fixed_essential: Dec;
  variable_essential: Dec;
  p2p_avg: Dec;
  survive: Dec;
  fixed_lifestyle: Dec;
  variable_lifestyle: Dec;
  live: Dec;
  savings_capacity: Dec;
  pace: Dec;
  accounts_total: Dec;
  reserved: Dec;
  free: Dec;
  emergency_months: number;
  fund_target: Dec | null;
  fund_current: Dec;
  fund_missing: Dec | null;
  fund_months_covered: Dec | null;
  fund_eta: string | null;
  rule_essential_pct: Dec | null;
  rule_lifestyle_pct: Dec | null;
  rule_savings_pct: Dec | null;
  goals: Goal[];
};

export type Allocation = {
  id: number;
  goal_id: number;
  account_id: number;
  account_name: string;
  currency: string;
  amount: Dec;
  allocated_on: string;
  notes: string | null;
};

export type Scenario = {
  income_avg: Dec;
  survive: Dec;
  current_lifestyle: Dec;
  lifestyle_target: Dec;
  live_target: Dec;
  savings_capacity: Dec;
  fund_months: Dec | null;
  required_income: Dec;
  max_lifestyle: Dec;
};
