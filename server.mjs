import express from 'express';
import { StreamableHttpServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { spawn } from 'child_process';

const app = express();
app.use(express.json());

const NEWS_CACHE_TTL_MS = Number(process.env.NEWS_CACHE_TTL_MS || 60000);
let newsCache = null;

function classifyArticle(article) {
  const text = `${article.title || ''} ${article.description || ''}`.toLowerCase();
  if (/rbi|sebi|policy|rate|inflation|budget|regulation|government/.test(text)) return 'POLICY';
  if (/f&o|future|option|open interest|strike|expiry|iv rank|pcr|rollover/.test(text)) return 'F&O';
  if (/asia|china|japan|us market|wall street|europe|global|fed|nasdaq|dow jones/.test(text)) return 'GLOBAL';
  if (/bank|it stocks|auto|pharma|metal|energy|realty|fmcg|sector/.test(text)) return 'SECTOR';
  return 'MARKET';
}

function sentimentForArticle(article) {
  const text = `${article.title || ''} ${article.description || ''}`.toLowerCase();
  if (/gain|rise|rally|positive|surge|beat|upgrade|inflow|growth/.test(text)) return 'POSITIVE';
  if (/fall|drop|loss|negative|sell|downgrade|outflow|cut|crisis/.test(text)) return 'NEGATIVE';
  return 'NEUTRAL';
}

function impactForArticle(article) {
  const text = `${article.title || ''} ${article.description || ''}`.toLowerCase();
  if (/rbi|sebi|rate decision|inflation|budget|halt|crash|surge|war/.test(text)) return 'HIGH';
  if (/earnings|results|upgrade|downgrade|acquisition|ipo|open interest/.test(text)) return 'MEDIUM';
  return 'LOW';
}

function normalizeArticle(article, index) {
  const source = article.source?.name || 'Unknown source';
  const publishedAt = article.publishedAt || new Date().toISOString();
  return {
    id: article.url || `${source}-${publishedAt}-${index}`,
    publishedAt,
    category: classifyArticle(article),
    title: article.title || 'Untitled market update',
    summary: article.description || undefined,
    source,
    sourceUrl: article.url || '#',
    sentiment: sentimentForArticle(article),
    impact: impactForArticle(article),
  };
}

function makeStats(items) {
  return {
    headlines: items.length,
    highImpact: items.filter((item) => item.impact === 'HIGH').length,
    positive: items.filter((item) => item.sentiment === 'POSITIVE').length,
    neutral: items.filter((item) => item.sentiment === 'NEUTRAL').length,
  };
}

async function fetchNewsData() {
  if (!process.env.NEWS_API_KEY) throw new Error('NEWS_API_KEY is not configured');
  const query = encodeURIComponent('NIFTY OR BANKNIFTY OR NSE OR BSE OR RBI OR SEBI OR Indian stock market');
  const url = `https://newsapi.org/v2/everything?q=${query}&language=en&sortBy=publishedAt&pageSize=100`;
  const response = await fetch(url, { headers: { 'X-Api-Key': process.env.NEWS_API_KEY } });
  if (!response.ok) throw new Error(`News provider returned ${response.status}`);
  const payload = await response.json();
  const items = (payload.articles || [])
    .filter((article) => article.title && article.title !== '[Removed]')
    .map(normalizeArticle)
    .filter((item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index);
  const events = await fetchMarketEvents();
  return { items, events, stats: makeStats(items), fetchedAt: new Date().toISOString() };
}

async function fetchMarketEvents() {
  if (!process.env.MARKET_EVENTS_URL) return [];
  try {
    const response = await fetch(process.env.MARKET_EVENTS_URL);
    if (!response.ok) throw new Error(`Event provider returned ${response.status}`);
    const payload = await response.json();
    const events = Array.isArray(payload) ? payload : payload.events || [];
    return events.filter((event) => event.title && event.eventAt).map((event, index) => ({
      id: event.id || `event-${event.eventAt}-${index}`,
      eventAt: event.eventAt,
      timezone: event.timezone || 'Asia/Kolkata',
      title: event.title,
      country: event.country,
      impact: ['HIGH', 'MEDIUM', 'LOW'].includes(event.impact) ? event.impact : 'MEDIUM',
      status: ['UPCOMING', 'RELEASED', 'CANCELLED'].includes(event.status) ? event.status : 'UPCOMING',
      actual: event.actual,
      forecast: event.forecast,
      previous: event.previous,
    }));
  } catch (error) {
    console.warn(`Market event feed unavailable: ${error.message}`);
    return [];
  }
}

app.get('/api/news', async (req, res) => {
  if (newsCache && Date.now() - newsCache.createdAt < NEWS_CACHE_TTL_MS) return res.json(newsCache.data);
  try {
    const data = await fetchNewsData();
    newsCache = { createdAt: Date.now(), data };
    return res.json(data);
  } catch (error) {
    return res.status(503).json({ error: error.message, cached: Boolean(newsCache), data: newsCache?.data || null });
  }
});

// 1. Health check for Claude auto-discovery
app.get('/', (req, res) => {
  res.status(200).send('MCP Server Active');
});

// 2. Streamable HTTP endpoint for Claude Web
app.all('/mcp', async (req, res) => {
  const mcpProcess = spawn('mcp-server-github', [], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'inherit']
  });

  const transport = new StreamableHttpServerTransport(req, res);
  
  // Connect MCP SDK transport to GitHub binary stdio
  mcpProcess.stdout.pipe(transport.outboundStream);
  transport.inboundStream.pipe(mcpProcess.stdin);

  req.on('close', () => mcpProcess.kill());
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`MCP HTTP Bridge running on port ${PORT}`);
});
