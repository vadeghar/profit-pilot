import type { Candle, Position, Quote } from '../types/market';

export const initialQuotes: Quote[] = [
  { symbol: 'NIFTY 50', exchange: 'NSE INDEX', price: 24833.15, previousPrice: 24690.55, change: 142.60, changePct: 0.58, volume: 235420000, updatedAt: Date.now() },
  { symbol: 'BANKNIFTY', exchange: 'NSE INDEX', price: 50212.45, previousPrice: 49955.55, change: 256.90, changePct: 0.51, volume: 128190000, updatedAt: Date.now() },
  { symbol: 'RELIANCE', exchange: 'NSE EQ', price: 2945.80, previousPrice: 2958.25, change: -12.45, changePct: -0.42, volume: 18330000, updatedAt: Date.now() },
  { symbol: 'TCS', exchange: 'NSE EQ', price: 3842.35, previousPrice: 3823.60, change: 18.75, changePct: 0.49, volume: 5420000, updatedAt: Date.now() },
  { symbol: 'HDFCBANK', exchange: 'NSE EQ', price: 1676.20, previousPrice: 1668.00, change: 8.20, changePct: 0.49, volume: 14720000, updatedAt: Date.now() },
  { symbol: 'INFY', exchange: 'NSE EQ', price: 1502.35, previousPrice: 1509.15, change: -6.80, changePct: -0.45, volume: 7110000, updatedAt: Date.now() },
  { symbol: 'ICICIBANK', exchange: 'NSE EQ', price: 1239.85, previousPrice: 1235.25, change: 4.60, changePct: 0.37, volume: 9830000, updatedAt: Date.now() },
  { symbol: 'HINDUNILVR', exchange: 'NSE EQ', price: 2542.10, previousPrice: 2551.45, change: -9.35, changePct: -0.37, volume: 3190000, updatedAt: Date.now() },
];

export const positions: Position[] = [
  { symbol: 'NIFTY 29 MAY 24500 CE', side: 'BUY', qty: 75, avgPrice: 182.35, ltp: 198.70, pnl: 1226.25, pnlPct: 8.96 },
  { symbol: 'BANKNIFTY 29 MAY 50000 PE', side: 'SELL', qty: 50, avgPrice: 245.40, ltp: 238.10, pnl: 365.00, pnlPct: 2.97 },
  { symbol: 'RELIANCE EQ', side: 'BUY', qty: 100, avgPrice: 2910.00, ltp: 2945.80, pnl: 3580.00, pnlPct: 1.23 },
];

export const marketNews = [
  ['10:16', 'NIFTY 50 expands gains as banking stocks lead the rally'],
  ['10:11', 'RBI keeps policy rates unchanged, maintains accommodative stance'],
  ['10:05', 'Global markets mixed ahead of US CPI data release'],
  ['09:58', 'IT stocks recover after early-session selling pressure'],
];

export const candles: Candle[] = Array.from({ length: 72 }, (_, i) => {
  const base = 24760 + i * 1.02 + Math.sin(i / 5) * 28 + Math.sin(i * 1.8) * 7;
  const open = base;
  const close = base + Math.sin(i * 1.35) * 10 + (i % 7 === 0 ? 5 : 0);
  const high = Math.max(open, close) + 5 + Math.abs(Math.sin(i)) * 5;
  const low = Math.min(open, close) - 5 - Math.abs(Math.cos(i * .7)) * 4;
  return { time: `${String(9 + Math.floor((i + 30) / 60)).padStart(2, '0')}:${String((30 + i) % 60).padStart(2, '0')}`, open, high, low, close, volume: 900000 + Math.round(Math.abs(Math.sin(i * 1.3)) * 1300000) };
});
