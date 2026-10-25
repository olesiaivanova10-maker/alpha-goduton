export interface Counterparty {
  company_id: string;
  direction: 'incoming' | 'outgoing';
  payment_amount: number;
  payment_count: number;
}

export interface CompanyContext {
  company_id: string;
  group_id: string | null;
  industry: { okved_code: string | null; name: string | null };
  organization: {
    type: string | null;
    ownership: string | null;
    age: string | null;
    development_stage: string | null;
  };
  location: { city: string | null; region: string | null };
  scale: {
    revenue: number | null;
    employees_fns: string | null;
    employees_spark: string | null;
  };
  
  bank_products: {
    rko: number;
    credit: number;
    leasing: number;
    guarantees: number;
    deposits: number;
    salary_project: number;
    factoring: number;
  };
  foreign_trade: { has_fts_data: number; country: string | null };
  group_companies: string[];
  related_persons: Record<string, unknown>[];
  counterparties: Counterparty[];
  warnings: string[];
}