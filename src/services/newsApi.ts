import { newsFallback } from '../data/newsFallback';
import type { NewsCategory, NewsItem, NewsResponse } from '../types/news';

const endpoint = import.meta.env.VITE_NEWS_API_URL || '/api/news';

export async function fetchNews(signal?: AbortSignal, forceRefresh = false): Promise<NewsResponse> {
  const url = forceRefresh ? `${endpoint}${endpoint.includes('?') ? '&' : '?'}force_refresh=true` : endpoint;
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`News service returned ${response.status}`);
  return response.json() as Promise<NewsResponse>;
}

export function categoryMatches(category: NewsCategory | 'ALL', item: NewsItem) {
  return category === 'ALL' || item.category === category;
}

export { newsFallback };
