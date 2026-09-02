export type AnalyticsFreshness = 'LIVE' | 'DELAYED' | 'EOD' | 'STALE' | 'UNAVAILABLE';

export type AnalyticsMeta = {
  asOf: string;
  source: string;
  freshness: AnalyticsFreshness;
  stale: boolean;
  errors: string[];
};

export type AnalyticsSnapshot = {
  summary: {
    advancers: number | null;
    decliners: number | null;
    advanceDeclineRatio: number | null;
    newHighs: number | null;
    newLows: number | null;
  };
  breadth: {
    advancingPercent: number | null;
    decliningPercent: number | null;
    unchanged: number | null;
  };
  momentumLeaders: Array<{
    symbol: string;
    name: string;
    price: number | null;
    changePct: number | null;
    volume: number | null;
    sparkline: number[];
  }>;
  volatility: Array<{
    name: string;
    value: number | null;
    changePct: number | null;
    unit: string;
  }>;
  marketCards: Record<string, Array<{
    symbol: string;
    name: string | null;
    price: number | null;
    changePct: number | null;
    volume: number | null;
    value: number | null;
  }>>;
  indices: Array<{ name: string; value: number | null; changePct: number | null }>;
  activeContracts: Record<string, Array<{ contract: string; symbol: string | null; price: number | null; changePct: number | null }>>;
  meta: AnalyticsMeta;
};

export const analyticsInitial: AnalyticsSnapshot = {
  summary: { advancers: null, decliners: null, advanceDeclineRatio: null, newHighs: null, newLows: null },
  breadth: { advancingPercent: null, decliningPercent: null, unchanged: null },
  momentumLeaders: [],
  volatility: [],
  marketCards: {},
  indices: [],
  activeContracts: {},
  meta: { asOf: '', source: '', freshness: 'UNAVAILABLE', stale: false, errors: [] },
};
