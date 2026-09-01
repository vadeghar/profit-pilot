export type NewsCategory = 'MARKET' | 'POLICY' | 'GLOBAL' | 'SECTOR' | 'F&O';
export type NewsSentiment = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
export type NewsImpact = 'HIGH' | 'MEDIUM' | 'LOW';

export type NewsItem = {
  id: string;
  publishedAt: string;
  category: NewsCategory;
  title: string;
  summary?: string;
  source: string;
  sourceUrl: string;
  sentiment: NewsSentiment;
  impact: NewsImpact;
  symbols?: string[];
  sectors?: string[];
};

export type MarketEvent = {
  id: string;
  eventAt: string;
  timezone: string;
  title: string;
  country?: string;
  category?: string;
  symbol?: string;
  fiscalPeriod?: string;
  impact: NewsImpact;
  status: 'UPCOMING' | 'RELEASED' | 'CANCELLED';
  actual?: string;
  forecast?: string;
  previous?: string;
};

export type NewsResponse = {
  items: NewsItem[];
  events: MarketEvent[];
  stats: { headlines: number; highImpact: number; positive: number; neutral: number };
  fetchedAt: string;
  sources?: { news: string[]; events: string[] };
  stale?: boolean;
  errors?: string[];
};
