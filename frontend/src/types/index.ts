export interface QueryRequest {
  query: string;
  user_id?: string;
  options?: Record<string, unknown>;
}

export interface AnalysisResult {
  summary: string;
  key_findings: string[];
  financial_metrics: Record<string, number | string>;
  risks: string[];
  opportunities: string[];
  sentiment: string | null;
  confidence_score: number;
}

export interface QueryResponse {
  response_id: string;
  query_id: string;
  content: string;
  format: string;
  analysis: AnalysisResult | null;
  sources: string[];
  disclaimers: string[];
  processing_time_ms: number;
  timestamp: string;
}

export interface MarketData {
  ticker: string;
  company_name: string;
  current_price: number;
  change_percent: number;
  volume: number;
  market_cap: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  timestamp: string;
  additional_data: Record<string, unknown>;
}

export interface NewsItem {
  title: string;
  source: string;
  url: string;
  published_at: string;
  summary: string | null;
  tickers: string[];
}

export interface HistoricalData {
  ticker: string;
  period: string;
  data: {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
  statistics: {
    min_price: number;
    max_price: number;
    avg_price: number;
    total_volume: number;
    price_change: number;
    price_change_percent: number;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  response?: QueryResponse;
  isLoading?: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  timestamp: string;
  components: Record<string, boolean>;
}
