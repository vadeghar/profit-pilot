import { analyticsInitial, type AnalyticsMeta, type AnalyticsSnapshot } from '../types/analytics';

type CardName = 'summary' | 'breadth' | 'momentumLeaders' | 'volatility' | 'marketCards' | 'activeContracts';
type StreamHandler = (card: CardName, data: unknown, meta: AnalyticsMeta) => void;

export function streamAnalytics(onCard: StreamHandler, onComplete: (snapshot: AnalyticsSnapshot) => void, onError: (error: Event) => void, forceRefresh = false, onStart?: () => void) {
  const controller = new AbortController();
  const cards: CardName[] = ['summary', 'breadth', 'momentumLeaders', 'volatility', 'marketCards', 'activeContracts'];
  const snapshot = structuredClone(analyticsInitial);
  onStart?.();
  void Promise.all(cards.map(async (card) => {
    const response = await fetch(`/api/analytics/card/${card}${forceRefresh ? '?force_refresh=true' : ''}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`Analytics ${card} request failed`);
    const payload = await response.json() as { card: CardName; data: unknown; meta: AnalyticsMeta };
    snapshot[payload.card] = payload.data as never;
    snapshot.meta = payload.meta;
    onCard(payload.card, payload.data, payload.meta);
  })).then(() => onComplete(snapshot)).catch((error) => {
    if (error.name !== 'AbortError') onError(new Event('error'));
  });
  return () => controller.abort();
}
