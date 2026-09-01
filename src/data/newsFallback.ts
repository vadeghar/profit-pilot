import type { NewsResponse } from '../types/news';

const now = Date.now();
const fallbackItems = [
  ['NIFTY extends gains; banks and autos lead intraday move.', 'MARKET', 'POSITIVE'],
  ['RBI policy commentary keeps rate-sensitive names in focus.', 'POLICY', 'NEUTRAL'],
  ['Asian markets trade mixed as investors await US macro data.', 'GLOBAL', 'NEUTRAL'],
  ['IT stocks recover after early-session selling pressure.', 'SECTOR', 'POSITIVE'],
  ['NIFTY options activity rises around 24,800 strike.', 'F&O', 'POSITIVE'],
];

export const newsFallback: NewsResponse = {
  items: fallbackItems.map(([title, category, sentiment], index) => ({
    id: `fallback-${index}`,
    publishedAt: new Date(now - index * 5 * 60_000).toISOString(),
    category: category as NewsResponse['items'][number]['category'],
    title,
    source: 'Profit Pilot Demo Feed',
    sourceUrl: '#',
    sentiment: sentiment as NewsResponse['items'][number]['sentiment'],
    impact: index === 1 ? 'HIGH' : 'MEDIUM',
  })),
  events: [
    ['10:30', 'India PMI', 'HIGH'], ['11:00', 'US Futures', 'MEDIUM'],
    ['13:30', 'Options OI update', 'MEDIUM'], ['15:30', 'Cash market close', 'HIGH'],
  ].map(([time, title, impact], index) => ({
    id: `event-${index}`,
    eventAt: `${new Date().toISOString().slice(0, 10)}T${time}:00+05:30`,
    timezone: 'Asia/Kolkata', title,
    impact: impact as NewsResponse['events'][number]['impact'], status: 'UPCOMING' as const,
  })),
  stats: { headlines: 5, highImpact: 2, positive: 3, neutral: 2 },
  fetchedAt: new Date(now).toISOString(),
};
