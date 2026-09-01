export type Quote = {
  symbol: string;
  exchange: string;
  price: number;
  previousPrice: number;
  change: number;
  changePct: number;
  volume: number;
  updatedAt: number;
};

export type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Position = {
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  pnlPct: number;
};

export type Side = 'BUY' | 'SELL';

export type OrderPlacement = {
  type: 'ORDER_PLACEMENT';
  symbol: string;
  side: Side;
  sidePrice: number;
  volume: number;
};

export type PriceTick = {
  type: 'PRICE_TICK';
  symbol: string;
  price: number;
  change?: number;
  changePct?: number;
  volume?: number;
};

export type MarketTick = PriceTick;
