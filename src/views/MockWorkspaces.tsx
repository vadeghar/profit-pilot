import type { ReactNode } from 'react';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Bell,
  CheckCircle2, Clock3, Download, Filter, Gauge, Layers3, LineChart,
  ListFilter, Newspaper, Play, Plus, RefreshCw, Search, ShieldCheck,
  Target, TrendingDown, TrendingUp, Wallet, XCircle, Zap
} from 'lucide-react';
import { Panel } from '../components/Panel';
import { initialQuotes, positions } from '../data/mockMarket';
import { categoryMatches, fetchNews, newsFallback } from '../services/newsApi';
import type { NewsCategory, NewsItem, NewsResponse } from '../types/news';

const n = (v:number, d=2) => v.toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
const money = (v:number) => `₹ ${n(v)}`;

const stocks = [
  ['RELIANCE','2,945.80','-12.45','-0.42%','18.33M'],['TCS','3,842.35','+18.75','+0.49%','5.42M'],
  ['HDFCBANK','1,676.20','+8.20','+0.49%','14.72M'],['INFY','1,502.35','-6.80','-0.45%','7.11M'],
  ['ICICIBANK','1,239.85','+4.60','+0.37%','9.83M'],['SBIN','825.40','+9.15','+1.12%','11.26M'],
  ['LT','3,612.50','+21.35','+0.59%','3.04M'],['AXISBANK','1,142.75','-3.20','-0.28%','6.87M'],
];
const orders = [
  ['ORD-10482','NIFTY 50','BUY','75','24,820.00','FILLED','09:54:21'],
  ['ORD-10481','BANKNIFTY','SELL','50','50,180.00','OPEN','09:51:08'],
  ['ORD-10480','NIFTY 24800 CE','BUY','75','182.50','FILLED','09:48:44'],
  ['ORD-10479','RELIANCE','BUY','100','2,938.00','CANCELLED','09:42:19'],
  ['ORD-10478','HDFCBANK','SELL','100','1,681.00','REJECTED','09:38:02'],
];
const alerts = [
  ['NIFTY 50 > 24,850','Price','24,833.15','WAITING','High'],
  ['BANKNIFTY < 50,000','Price','50,212.45','WAITING','Medium'],
  ['RELIANCE RSI > 70','Indicator','68.4','TRIGGERED','Medium'],
  ['NIFTY VWAP Cross','Strategy','24,821.80','TRIGGERED','High'],
];
const optionRows = [
  ['24,600','58.20','2,160','24,780','24,820','98.45','1,240'],
  ['24,650','72.35','2,410','24,760','24,840','112.30','1,185'],
  ['24,700','91.80','3,120','24,730','24,870','129.75','980'],
  ['24,750','118.40','4,020','24,690','24,910','151.20','860'],
  ['24,800','156.25','5,180','24,650','24,950','182.35','742'],
  ['24,850','201.10','4,620','24,610','25,000','218.40','690'],
];
function HeaderStats({items}:{items:[string,string,string?][]}) {
  return <div className="grid grid-cols-2 gap-px border-b border-[#21262D] bg-[#21262D] md:grid-cols-4">
    {items.map(([a,b,c])=><div key={a} className="bg-[#161B22] px-3 py-2"><div className="text-[10px] uppercase tracking-wider text-[#8B949E]">{a}</div><div className="num mt-1 text-sm">{b}</div>{c&&<div className="mt-0.5 text-[10px] text-[#8B949E]">{c}</div>}</div>)}
  </div>
}
function Table({headers,rows}:{headers:string[],rows:(string|number)[][]}) {
  return <div className="overflow-auto"><div className="min-w-[720px]">
    <div className={`grid grid-cols-${Math.min(headers.length,7)} border-b border-[#21262D] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-[#8B949E]`} style={{gridTemplateColumns:`repeat(${headers.length},minmax(0,1fr))`}}>
      {headers.map((h,i)=><span key={h} className={i>1?'text-right':''}>{h}</span>)}
    </div>
    {rows.map((r,ri)=><div key={ri} className="grid items-center border-b border-[#21262D] px-3 py-2.5 text-xs hover:bg-[#1c2229]" style={{gridTemplateColumns:`repeat(${headers.length},minmax(0,1fr))`}}>
      {r.map((v,i)=><span key={i} className={`${i>1?'text-right ':''}${String(v).includes('-')||String(v).includes('DOWN')?'text-[#F85149]':String(v).includes('+')||['FILLED','TRIGGERED','RUNNING','OPEN'].includes(String(v))?'text-[#2EA043]':''} ${i>0?'num':''}`}>{v}</span>)}
    </div>)}
  </div></div>
}
function MiniSpark({positive=true}:{positive?:boolean}) {
  const pts = positive ? '0,36 15,31 28,33 42,23 57,26 71,15 86,18 100,8' : '0,8 15,14 28,10 42,25 57,20 71,32 86,28 100,38';
  return <svg viewBox="0 0 100 44" className="h-10 w-24"><polyline points={pts} fill="none" stroke={positive?'#2EA043':'#F85149'} strokeWidth="2"/></svg>
}

export function DataWorkspace({title, subtitle, children, stats, actions}:{title:string,subtitle?:string,children:ReactNode,stats?:[string,string,string?][],actions?:ReactNode}) {
 return <div className="space-y-3">
  <div className="flex flex-wrap items-end justify-between gap-2"><div><h1 className="text-lg font-semibold">{title}</h1>{subtitle&&<p className="mt-0.5 text-xs text-[#8B949E]">{subtitle}</p>}</div>{actions||<div className="flex gap-2"><button className="flex h-8 items-center gap-2 border border-[#30363D] bg-[#161B22] px-3 text-xs text-[#8B949E] hover:text-white"><RefreshCw className="h-3.5 w-3.5"/>Refresh</button><button className="flex h-8 items-center gap-2 bg-[#2EA043] px-3 text-xs font-semibold"><Plus className="h-3.5 w-3.5"/>Create</button></div>}</div>
  {stats&&<HeaderStats items={stats}/>}
  {children}
 </div>
}

export function OrderBooksView(){
 const [symbol,setSymbol]=useState('NIFTY 50');
 const bids=[['24,832.90','1,125'],['24,832.75','860'],['24,832.60','1,940'],['24,832.45','720'],['24,832.30','2,210']];
 const asks=[['24,833.15','940'],['24,833.30','1,180'],['24,833.45','1,460'],['24,833.60','680'],['24,833.75','2,050']];
 return <DataWorkspace title="Order Books" subtitle="Level-2 market depth with mock exchange liquidity" stats={[['Spread','0.25'],['Bid Size','6,855'],['Ask Size','6,310'],['Imbalance','+4.1%']]}>
  <div className="grid gap-3 lg:grid-cols-[280px_minmax(0,1fr)]">
   <Panel title="Instruments"><div className="p-2">{['NIFTY 50','BANKNIFTY','RELIANCE','TCS','HDFCBANK','INFY'].map(x=><button onClick={()=>setSymbol(x)} key={x} className={`flex w-full justify-between border-l-2 px-3 py-2.5 text-xs ${symbol===x?'border-[#2EA043] bg-[#1c2229]':'border-transparent text-[#8B949E] hover:bg-[#1c2229]'}`}><span>{x}</span><span className="num">{x==='NIFTY 50'?'24,833.15':x==='BANKNIFTY'?'50,212.45':'—'}</span></button>)}</div></Panel>
   <Panel title={`${symbol} · Market Depth`}><div className="grid grid-cols-2 gap-3 p-3"><Depth title="BIDS" rows={bids} buy/><Depth title="ASKS" rows={asks}/></div><div className="border-t border-[#21262D] p-3"><div className="mb-2 text-[10px] uppercase tracking-wider text-[#8B949E]">Order flow</div><div className="h-3 overflow-hidden bg-[#F85149]"><div className="h-full bg-[#2EA043]" style={{width:'52%'}}/></div><div className="mt-2 flex justify-between text-[10px] text-[#8B949E]"><span>Bid 52%</span><span>Ask 48%</span></div></div></Panel>
  </div>
 </DataWorkspace>
}
function Depth({title,rows,buy=false}:{title:string,rows:string[][],buy?:boolean}){return <div><div className="grid grid-cols-2 border-b border-[#21262D] pb-2 text-[10px] text-[#8B949E]"><span>{title}</span><span className="text-right">QTY</span></div>{rows.map((r,i)=><div key={i} className="grid grid-cols-2 py-2 text-xs"><span className={`num ${buy?'text-[#2EA043]':'text-[#F85149]'}`}>{r[0]}</span><span className="num text-right">{r[1]}</span></div>)}</div>}

export function PortfolioView(){
 return <DataWorkspace title="Portfolio" subtitle="Holdings, allocation and risk snapshot" stats={[['Invested Capital',money(487250)],['Current Value',money(501845)],['Day P&L','+₹ 8,426','+1.72%'],['Total P&L','+₹ 14,595','+2.99%']]}>
  <div className="grid gap-3 xl:grid-cols-3"><Panel title="Allocation"><div className="space-y-3 p-4"><Allocation name="Financials" value={38}/><Allocation name="IT" value={24}/><Allocation name="Energy" value={18}/><Allocation name="Consumer" value={12}/><Allocation name="Others" value={8}/></div></Panel><Panel className="xl:col-span-2" title="Holdings"><Table headers={['Symbol','Qty','Avg Cost','LTP','Invested','Value','P&L']} rows={stocks.slice(0,6).map((s,i)=>[s[0],i%2?100:75,s[1],s[1],money(90000+i*12000),money(94000+i*12500),i===1?'+₹ 1,875':'+'+money(3200+i*240)])}/></Panel></div>
  <Panel title="Risk Snapshot"><div className="grid gap-3 p-3 md:grid-cols-4">{[['Gross Exposure','₹ 5.02L'],['Net Exposure','₹ 3.18L'],['Margin Used','41.8%'],['VaR (1D)','₹ 12,480']].map(x=><div key={x[0]} className="border border-[#21262D] p-3"><div className="text-[10px] uppercase tracking-wider text-[#8B949E]">{x[0]}</div><div className="num mt-2 text-base">{x[1]}</div></div>)}</div></Panel>
 </DataWorkspace>
}
function Allocation({name,value}:{name:string,value:number}){return <div><div className="mb-1 flex justify-between text-xs"><span>{name}</span><span className="num">{value}%</span></div><div className="h-2 bg-[#21262D]"><div className="h-full bg-[#8B949E]" style={{width:`${value}%`}}/></div></div>}

export function PositionsView(){
 return <DataWorkspace title="Positions" subtitle="Live open positions and mark-to-market" stats={[['Open Positions','3'],['Realized P&L','+₹ 18,420'],['Unrealized P&L','+₹ 5,171'],['Margin','₹ 1.42L']]}>
 <Panel title="Open Positions"><Table headers={['Instrument','Side','Qty','Avg','LTP','P&L','P&L %']} rows={positions.map(p=>[p.symbol,p.side,p.qty,n(p.avgPrice),n(p.ltp),`${p.pnl>=0?'+':''}${n(p.pnl)}`,`${p.pnlPct>=0?'+':''}${p.pnlPct.toFixed(2)}%`])}/></Panel>
 <div className="grid gap-3 md:grid-cols-3">{[['Day P&L','+₹ 5,171','+2.15%'],['Charges','₹ 684.25',''],['Available Margin','₹ 2,04,880','']].map(x=><Panel key={x[0]} title={x[0]}><div className={`p-4 num text-xl ${x[1].startsWith('+')?'text-[#2EA043]':''}`}>{x[1]}<span className="ml-2 text-xs text-[#8B949E]">{x[2]}</span></div></Panel>)}</div>
 </DataWorkspace>
}

export function AlertsView(){
 const [rows,setRows]=useState(alerts);
 return <DataWorkspace title="Alert Manager" subtitle="Price, indicator and strategy event rules" stats={[['Active','18'],['Triggered Today','7'],['Muted','3'],['Delivery','WebSocket + UI']]}>
  <Panel title="Alert Rules"><Table headers={['Rule','Type','Value','Status','Priority','Action']} rows={rows.map((r,i)=>[...r,'View'])}/></Panel>
  <Panel title="Recent Events"><div className="divide-y divide-[#21262D]">{['10:12:14 NIFTY VWAP Cross triggered at 24,821.80','09:58:41 RELIANCE RSI returned below 70','09:46:08 BANKNIFTY crossed 50,200','09:39:55 NIFTY volume spike +42%'].map((x,i)=><div key={i} className="flex items-center gap-3 p-3 text-xs"><Bell className="h-4 w-4 text-[#2EA043]"/><span>{x}</span><span className="ml-auto text-[10px] text-[#8B949E]">today</span></div>)}</div></Panel>
 </DataWorkspace>
}

export function HistoryView(){
 return <DataWorkspace title="Trade History" subtitle="Execution ledger and order audit trail" stats={[['Orders Today','42'],['Filled','31'],['Rejected','2'],['Turnover','₹ 18.42L']]}>
  <Panel title="Execution History"><div className="flex flex-wrap gap-2 border-b border-[#21262D] p-3"><button className="h-8 border border-[#30363D] px-3 text-xs"><Filter className="mr-2 inline h-3.5 w-3.5"/>All Status</button><button className="h-8 border border-[#30363D] px-3 text-xs">Today</button><button className="h-8 border border-[#30363D] px-3 text-xs">All Segments</button><button className="ml-auto h-8 border border-[#30363D] px-3 text-xs"><Download className="mr-2 inline h-3.5 w-3.5"/>Export</button></div><Table headers={['Order ID','Symbol','Side','Qty','Price','Status','Time']} rows={orders}/></Panel>
 </DataWorkspace>
}

export function StrategyView(){
 const strategies=[['RSI Momentum','NIFTY 50 · 5m','LIVE','68.4%','+₹ 42,680','24'],['VWAP Reversion','BANKNIFTY · 1m','PAUSED','61.2%','+₹ 18,420','17'],['Opening Range Breakout','NIFTY Options · 5m','BACKTEST','64.8%','+₹ 76,240','31']];
 return <DataWorkspace title="Strategy Builder" subtitle="Design, test and deploy rule-based strategies" stats={[['Strategies','12'],['Live','3'],['Backtests','84'],['Net Strategy P&L','+₹ 1.82L']]}>
  <div className="grid gap-3 lg:grid-cols-3">{strategies.map(s=><Panel key={s[0]} title={s[0]}><div className="p-4"><div className="text-xs text-[#8B949E]">{s[1]}</div><div className="mt-3 flex items-center justify-between"><span className={`text-[10px] font-semibold ${s[2]==='LIVE'?'text-[#2EA043]':'text-[#8B949E]'}`}>{s[2]}</span><span className="num text-lg">{s[3]}</span></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div className="border border-[#21262D] p-2"><div className="text-[9px] text-[#8B949E]">P&L</div><div className="num text-[#2EA043]">{s[4]}</div></div><div className="border border-[#21262D] p-2"><div className="text-[9px] text-[#8B949E]">TRADES</div><div className="num">{s[5]}</div></div></div><button className="mt-3 flex h-8 w-full items-center justify-center gap-2 border border-[#30363D] text-xs hover:bg-[#21262D]"><Play className="h-3.5 w-3.5"/>Open Strategy</button></div></Panel>)}</div>
  <Panel title="Strategy Performance"><div className="p-4"><div className="flex h-44 items-end gap-2">{[25,38,32,48,42,57,63,59,72,66,82,91,87,96,100].map((v,i)=><div key={i} className="flex-1 bg-[#2EA043]" style={{height:`${v}%`,opacity:.45+i/35}} title={`Day ${i+1}`}/>)}</div><div className="mt-2 flex justify-between text-[10px] text-[#8B949E]"><span>D-15</span><span>D-7</span><span>Today</span></div></div></Panel>
 </DataWorkspace>
}

export function NewsView(){
 const [filter,setFilter]=useState<NewsCategory|'ALL'>('ALL');
 const [data,setData]=useState<NewsResponse>(newsFallback);
 const [loading,setLoading]=useState(false);
 const [error,setError]=useState<string|null>(null);
 const loadNews=async(forceRefresh=false)=>{
  setLoading(true); setError(null);
  try { setData(await fetchNews(undefined, forceRefresh)); }
  catch { setError('Live feed unavailable; showing the latest cached demo feed.'); }
  finally { setLoading(false); }
 };
 useEffect(()=>{ void loadNews(); const id=window.setInterval(()=>void loadNews(), 60_000); return()=>window.clearInterval(id); },[]);
 const filtered=data.items.filter(item=>categoryMatches(filter,item));
 const formatTime=(value:string)=>new Intl.DateTimeFormat('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));
 const stats:[string,string][]=[['Headlines',String(data.stats.headlines)],['High Impact',String(data.stats.highImpact)],['Positive',String(data.stats.positive)],['Neutral',String(data.stats.neutral)]];
 const sourceLabel=data.sources?.news?.join(' + ') || 'fallback';
 const refreshButton=<button onClick={()=>void loadNews(true)} disabled={loading} className="flex h-8 items-center gap-2 border border-[#30363D] bg-[#161B22] px-3 text-xs text-[#8B949E] hover:text-white disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw className={`h-3.5 w-3.5 ${loading?'animate-spin':''}`}/>Refresh</button>;
 return <DataWorkspace title="Market News" subtitle="Live market headlines and event context" stats={stats} actions={<div className="flex gap-2">{refreshButton}</div>}>
  <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_300px]">
   <Panel title="News Feed"><div className="flex gap-1 border-b border-[#21262D] p-2">{['ALL','MARKET','POLICY','GLOBAL','SECTOR','F&O'].map(x=><button onClick={()=>setFilter(x as NewsCategory|'ALL')} key={x} className={`px-3 py-1.5 text-[10px] ${filter===x?'bg-[#2EA043] text-white':'text-[#8B949E] hover:bg-[#21262D]'}`}>{x}</button>)}</div>{error&&<div className="border-b border-[#21262D] px-3 py-2 text-[10px] text-[#D29922]">{error}</div>}<div className="divide-y divide-[#21262D]">{filtered.map((item:NewsItem)=><article key={item.id} className="p-3 hover:bg-[#1c2229]"><div className="flex items-center gap-2 text-[10px] text-[#8B949E]"><span className="num">{formatTime(item.publishedAt)}</span><span>·</span><span>{item.category}</span><span className={`ml-auto ${item.sentiment==='POSITIVE'?'text-[#2EA043]':item.sentiment==='NEGATIVE'?'text-[#F85149]':'text-[#8B949E]'}`}>{item.sentiment[0]+item.sentiment.slice(1).toLowerCase()}</span></div><a href={item.sourceUrl} target="_blank" rel="noreferrer" className="mt-1 block text-sm hover:text-[#2EA043]">{item.title}</a><div className="mt-2 text-[10px] text-[#8B949E]">Source: {item.source}</div></article>)}{!filtered.length&&<div className="p-6 text-center text-xs text-[#8B949E]">No headlines in this section.</div>}</div></Panel>
   <Panel title="Market Events"><div className="space-y-3 p-3">{data.events.map(event=><div key={event.id} className="flex gap-3 border-b border-[#21262D] pb-3 last:border-0"><Clock3 className="mt-0.5 h-4 w-4 text-[#8B949E]"/><div><div className="num text-xs">{formatTime(event.eventAt)}</div><div className="text-xs">{event.title}</div><div className="text-[9px] text-[#8B949E]">{[event.symbol,event.category].filter(Boolean).join(' · ')}{event.symbol||event.category?' · ':''}{event.impact[0]+event.impact.slice(1).toLowerCase()} impact</div></div></div>)}{!data.events.length&&<div className="text-xs text-[#8B949E]">No upcoming events.</div>}</div></Panel>
  </div>
  <div className="flex justify-between text-[10px] text-[#8B949E]"><span>Feed: {sourceLabel}{data.stale?' · stale':''}</span><span>{loading?'Updating news feed...':`Updated ${formatTime(data.fetchedAt)}`}</span></div>
 </DataWorkspace>
}

export function AnalyticsView(){
 const sectorPerformance:[string,number][]=[['Banking',1.42],['Auto',1.18],['IT',.64],['Energy',.51],['FMCG',-.28],['Pharma',-.46],['Metal',-.72],['Realty',-1.05]];
 return <DataWorkspace title="Analytics" subtitle="Market breadth, momentum and performance analytics" stats={[['Advancers','1,482'],['Decliners','936'],['New Highs','118'],['New Lows','47']]}>
  <div className="grid gap-3 lg:grid-cols-3"><Panel title="Market Breadth"><div className="p-4"><div className="num text-3xl">1.58</div><div className="mt-1 text-xs text-[#8B949E]">Advance / decline ratio</div><div className="mt-5 h-3 bg-[#F85149]"><div className="h-full bg-[#2EA043]" style={{width:'61%'}}/></div><div className="mt-2 flex justify-between text-[10px] text-[#8B949E]"><span>1,482 Adv</span><span>936 Dec</span></div></div></Panel><Panel title="Momentum Leaders"><div className="divide-y divide-[#21262D]">{stocks.slice(0,5).map((s,i)=><div key={s[0]} className="flex items-center p-3"><span className="w-5 num text-[#8B949E]">{i+1}</span><span className="flex-1">{s[0]}</span><span className="num text-[#2EA043]">{s[3]}</span><MiniSpark/></div>)}</div></Panel><Panel title="Volatility"><div className="space-y-4 p-4">{[['India VIX','13.42','-3.8%'],['NIFTY ATR','118.6','+4.2%'],['BANKNIFTY ATR','284.3','+6.1%'],['Put/Call OI','1.08','+0.04']].map(x=><div key={x[0]} className="flex justify-between border-b border-[#21262D] pb-3"><span className="text-xs text-[#8B949E]">{x[0]}</span><span className="num">{x[1]} <span className="ml-2 text-[#8B949E]">{x[2]}</span></span></div>)}</div></Panel></div>
  <Panel title="Sector Performance"><div className="grid gap-2 p-3 md:grid-cols-2">{sectorPerformance.map(x=><div key={x[0]} className="flex items-center gap-3"><span className="w-20 text-xs">{x[0]}</span><div className="h-5 flex-1 bg-[#21262D]"><div className={`h-full ${x[1]>=0?'bg-[#2EA043]':'bg-[#F85149]'}`} style={{width:`${Math.min(100,Math.abs(x[1])*45)}%`}}/></div><span className={`num w-16 text-right ${x[1]>=0?'text-[#2EA043]':'text-[#F85149]'}`}>{x[1]>=0?'+':''}{x[1].toFixed(2)}%</span></div>)}</div></Panel>
 </DataWorkspace>
}

export function ToolsView(){
 return <DataWorkspace title="Tools" subtitle="Trading utilities and market calculators" stats={[['Calculators','8'],['Watch Tools','5'],['Scanners','12'],['Utilities','9']]}><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[
 ['Position Sizer','Calculate quantity from risk budget',Gauge],['Option Payoff','Visualize expiry payoff',LineChart],['Market Scanner','Scan price and volume conditions',ListFilter],['F&O Calculator','Estimate margin and P&L',Wallet],['Pivot Calculator','Classic / Fibonacci pivots',Target],['Risk Calculator','Stop loss and R:R planning',ShieldCheck],['Correlation','Compare instrument relationships',Activity],['Session Timer','Track market session phases',Clock3]
 ].map(([a,b,I])=><Panel key={a as string} title={a as string}><div className="p-4"><I className="h-6 w-6 text-[#8B949E]"/><div className="mt-3 text-sm">{a as string}</div><div className="mt-1 text-[11px] text-[#8B949E]">{b as string}</div><button className="mt-4 h-8 w-full border border-[#30363D] text-xs hover:bg-[#21262D]">Open Tool</button></div></Panel>)}</div></DataWorkspace>
}

export function SettingsView(){
 const [auto,setAuto]=useState(true); const [sound,setSound]=useState(false);
 return <DataWorkspace title="Settings" subtitle="Profit Pilot terminal configuration" stats={[['Connection','Connected'],['Data Feed','Mock NSE'],['Latency','42 ms'],['Environment','Development']]}>
 <div className="grid gap-3 lg:grid-cols-2"><Panel title="Market Data"><Setting label="Live tick simulation" value={auto} setValue={setAuto}/><Setting label="Price flash animations" value={true} setValue={()=>{}}/><Setting label="Compact market depth" value={true} setValue={()=>{}}/></Panel><Panel title="Notifications"><Setting label="Order confirmations" value={true} setValue={()=>{}}/><Setting label="Alert sounds" value={sound} setValue={setSound}/><Setting label="News high-impact alerts" value={true} setValue={()=>{}}/></Panel><Panel title="Execution"><div className="space-y-3 p-3">{[['Default Product','MIS'],['Default Order Type','LIMIT'],['Default Quantity','1 LOT'],['Confirmation Mode','STANDARD']].map(x=><div key={x[0]} className="flex items-center justify-between border-b border-[#21262D] pb-3 text-xs"><span className="text-[#8B949E]">{x[0]}</span><select className="border border-[#30363D] bg-[#0D1117] px-3 py-1.5 text-xs"><option>{x[1]}</option><option>NRML</option><option>MARKET</option></select></div>)}</div></Panel><Panel title="WebSocket"><div className="space-y-3 p-3">{[['Endpoint','ws://localhost:8000/ws'],['Protocol','profit-pilot.v1'],['Reconnect','Automatic'],['Heartbeat','30 seconds']].map(x=><div key={x[0]} className="flex justify-between border-b border-[#21262D] pb-3 text-xs"><span className="text-[#8B949E]">{x[0]}</span><span className="num">{x[1]}</span></div>)}</div></Panel></div>
 </DataWorkspace>
}
function Setting({label,value,setValue}:{label:string,value:boolean,setValue:(v:boolean)=>void}){return <div className="flex items-center justify-between border-b border-[#21262D] p-3 text-xs"><span>{label}</span><button onClick={()=>setValue(!value)} className={`relative h-5 w-9 rounded-full ${value?'bg-[#2EA043]':'bg-[#30363D]'}`}><span className={`absolute top-1 h-3 w-3 rounded-full bg-white transition-all ${value?'left-5':'left-1'}`}/></button></div>}

export function WatchlistsMockView(){
 const [search,setSearch]=useState('');
 const rows=initialQuotes.filter(q=>q.symbol.toLowerCase().includes(search.toLowerCase()));
 return <DataWorkspace title="Watchlists" subtitle="Multiple symbol lists with live mock quotes" stats={[['Instruments','8'],['Advancing','5'],['Declining','3'],['Last Update','10:16:24']]}>
  <Panel title="My Watchlist"><div className="flex gap-2 border-b border-[#21262D] p-3"><div className="relative flex-1"><Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#8B949E]"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter symbols..." className="h-8 w-full border border-[#30363D] bg-[#0D1117] pl-8 pr-3 text-xs outline-none focus:border-[#2EA043]"/></div><button className="h-8 border border-[#30363D] px-3 text-xs">Indices</button><button className="h-8 border border-[#30363D] px-3 text-xs">Equities</button></div><Table headers={['Symbol','Exchange','Last','Change','Change %','Volume']} rows={rows.map(q=>[q.symbol,q.exchange,n(q.price),`${q.change>=0?'+':''}${n(q.change)}`,`${q.changePct>=0?'+':''}${q.changePct.toFixed(2)}%`,q.volume.toLocaleString('en-IN')])}/></Panel>
 </DataWorkspace>
}

export function OptionsView({kind='Options'}:{kind?:string}){
 return <DataWorkspace title={kind} subtitle={`Derivative chain and market statistics · mock ${kind.toLowerCase()} feed`} stats={[['Underlying','NIFTY 50'],['Spot','24,833.15'],['Expiry','29 May 2026'],['IV Rank','42.8']]}>
  <Panel title="Option Chain"><div className="overflow-auto"><table className="min-w-[900px] w-full text-xs"><thead><tr className="border-b border-[#21262D] text-[10px] text-[#8B949E]"><th colSpan={3} className="p-2 text-center text-[#2EA043]">CALLS</th><th className="p-2">STRIKE</th><th colSpan={3} className="p-2 text-center text-[#F85149]">PUTS</th></tr><tr className="border-b border-[#21262D] text-[10px] text-[#8B949E]">{['OI','LTP','IV','STRIKE','IV','LTP','OI'].map(x=><th key={x} className="p-2 text-right">{x}</th>)}</tr></thead><tbody>{optionRows.map((r,i)=><tr key={i} className={`border-b border-[#21262D] ${r[0]==='24,800'?'bg-[#1c2229]':''}`}>{r.map((v,j)=><td key={j} className={`p-2 text-right num ${j===3?'font-semibold text-white':''}`}>{v}</td>)}</tr>)}</tbody></table></div></Panel>
 </DataWorkspace>
}
export function SpotTradingView(){
 return <DataWorkspace title="Spot Trading" subtitle="Equity execution workspace" stats={[['NIFTY 50','24,833.15','+0.58%'],['BANKNIFTY','50,212.45','+0.51%'],['Buying Power','₹ 4.82L'],['Connection','LIVE MOCK']]}>
 <div className="grid gap-3 lg:grid-cols-[1.5fr_1fr]"><Panel title="Market Watch"><Table headers={['Symbol','Last','Change','Change %','Volume']} rows={stocks.map(s=>[s[0],s[1],s[2],s[3],s[4]])}/></Panel><QuickOrder/></div>
 </DataWorkspace>
}
function QuickOrder(){const [side,setSide]=useState('BUY'); return <Panel title="Quick Order"><div className="p-4"><div className="grid grid-cols-2 gap-1 bg-[#0D1117] p-1">{['BUY','SELL'].map(x=><button key={x} onClick={()=>setSide(x)} className={`h-9 text-xs font-semibold ${side===x?(x==='BUY'?'bg-[#2EA043]':'bg-[#F85149]'):'text-[#8B949E]'}`}>{x}</button>)}</div>{['Symbol','Price','Quantity','Order Type'].map((x,i)=><div key={x} className="mt-3"><label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">{x}</label>{x==='Order Type'?<select className="h-9 w-full border border-[#30363D] bg-[#0D1117] px-3 text-xs"><option>LIMIT</option><option>MARKET</option></select>:<input className="num h-9 w-full border border-[#30363D] bg-[#0D1117] px-3 text-right text-xs outline-none focus:border-[#2EA043]" defaultValue={i===0?'NIFTY 50':i===1?'24833.15':'75'}/>}</div>)}<button className={`mt-4 h-10 w-full font-semibold ${side==='BUY'?'bg-[#2EA043]':'bg-[#F85149]'}`}>PLACE {side}</button></div></Panel>}
export function DerivativesView(){return <OptionsView kind="Derivatives"/>}
export function AlgoOrdersView(){
 return <DataWorkspace title="Algorithmic Orders" subtitle="Mock execution strategies and order automation" stats={[['Running','4'],['Queued','7'],['Completed','128'],['Success Rate','96.2%']]}>
  <Panel title="Algo Order Blotter"><Table headers={['Algo ID','Strategy','Symbol','Side','Qty','Status','Progress']} rows={[
   ['ALGO-884','TWAP','NIFTY 50','BUY','750','RUNNING','62%'],
   ['ALGO-883','VWAP','BANKNIFTY','SELL','500','RUNNING','41%'],
   ['ALGO-882','ICEBERG','RELIANCE','BUY','1,000','QUEUED','0%'],
   ['ALGO-881','TWAP','TCS','SELL','250','COMPLETED','100%']
  ]}/></Panel>
 </DataWorkspace>
}
export function PerpetualsView(){
 return <DataWorkspace title="Perpetuals" subtitle="Mock perpetual futures trading and funding monitor" stats={[['BTC-INR PERP','₹ 9,142,800'],['Funding','+0.012%'],['Open Interest','₹ 82.4Cr'],['24h Volume','₹ 1,184Cr']]}>
  <Panel title="Perpetual Contracts"><Table headers={['Contract','Mark','Index','Funding','OI','24h Change']} rows={[
   ['NIFTY PERP','24,842.10','24,833.15','+0.008%','₹ 42.8Cr','+0.72%'],
   ['BANKNIFTY PERP','50,248.40','50,212.45','+0.014%','₹ 31.2Cr','+0.58%'],
   ['BTC-INR PERP','91,42800','91,40200','+0.012%','₹ 82.4Cr','-0.34%']
  ]}/></Panel>
 </DataWorkspace>
}
export function FuturesView(){return <OptionsView kind="Futures Contracts"/>}
