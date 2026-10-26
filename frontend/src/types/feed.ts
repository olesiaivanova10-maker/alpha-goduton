export type UserRole = 'CEO' | 'CFO' | 'TREASURER';

export type ContentOrigin =
  | 'ФАКТ'
  | 'ПОЗИЦИЯ БАНКА'
  | 'ВЫВОД ИИ'
  | 'РЕКОМЕНДАЦИЯ БАНКА'
  | 'ИСТОЧНИКИ';

export interface ClientFeaturesSummary {
  matched_okved: string;
  revenue_rub: number;
  has_loans: boolean;
  has_leasing: boolean;
  has_deposits: boolean;
  foreign_trade_countries?: string | null;
  influencing_signals: string[];
}

export interface EventRelevance {
  score: number; // 0..1
  is_critical: boolean;
  rationale: string;
  affected_areas: string[];
}

export interface SourceItem {
  type: string;
  name: string;
  url_or_file?: string | null;
  page?: number | null;
}

export interface SixQuestionsCard {
  q1_what_happened: { question: string; origin: ContentOrigin; text: string };
  q2_why_matters: { question: string; origin: ContentOrigin; text: string };
  q3_bank_evaluation: {
    question: string;
    origin: ContentOrigin;
    text: string;
    has_report: boolean;
    bank_excerpts?: {text: string; filename: string; page: number; report_date?: string | null; extraction_method: string}[];
    report_title?: string | null;
    source_file?: string | null;
  };
  q4_consequences: {
    question: string;
    origin: ContentOrigin;
    risks: string[];
    opportunities: string[];
  };
  q5_recommended_actions: {
    question: string;
    origin: ContentOrigin;
    action_type: string;
    title: string;
    description: string;
    bank_product_tag?: string | null;
    button_text: string;
  };
  q6_basis_of_conclusion: {
    question: string;
    origin: ContentOrigin;
    sources: SourceItem[];
    client_signals_used: string[];
  };
}

export interface EventCard {
  card_id: string;
  news_id: string;
  published_at?: string | null;
  title: string;
  relevance: EventRelevance;
  client_features: ClientFeaturesSummary;
  six_questions: SixQuestionsCard;
  disclaimer: string;
  analysis_status?: string;
}

export interface NewsFeedResponse {
  company_id: string;
  company_name: string;
  target_role: UserRole;
  total_events: number;
  critical_events_count: number;
  events: EventCard[];
}