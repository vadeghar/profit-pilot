import { BarChart3, Maximize2, MoreHorizontal, Settings, Star, Crosshair } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { Panel } from '../components/Panel';
import { candles, initialQuotes, marketNews, positions } from '../data/mockMarket';
import { useWebSocket } from '../context/WebSocketContext';
import type { Candle, Quote } from '../types/market';

const fmt = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function WatchlistsView() {
  const [quotes, setQuotes] = useState(initialQuotes);
  const [flashes, setFlashes] = useState<Record<string, 'up' | 'down'>>({});
  const [activeSymbol, setActiveSymbol] = useState('NIFTY 50');
  const { subscribe } = useWebSocket();

  useEffect(() => subscribe((tick) => {
    setQuotes(current => current.map(q => {
      if (q.symbol !== tick.symbol) return q;
      const direction = tick.price >= q.price ? 'up' : 'down';
      setFlashes(f => ({ ...f, [tick.symbol]: direction }));
      window.setTimeout(() => setFlashes(f => { const n = { ...f }; delete n[tick.symbol]; return n; }), 300);
      return { ...q, previousPrice: q.price, price: tick.price, change: tick.change ?? tick.price - q.previousPrice, changePct: tick.changePct ?? ((tick.price - q.previousPrice) / q.previousPrice) * 100, volume: tick.volume ?? q.volume, updatedAt: Date.now() };
    }));
  }), [subscribe]);

  useEffect(() => {
    if (import.meta.env.VITE_WS_URL) return;
    const id = window.setInterval(() => setQuotes(current => current.map(q => {
      const step = Math.max(0.05, q.price * (Math.random() * 0.00012));
      const next = +(q.price + (Math.random() > .48 ? step : -step)).toFixed(2);
      return { ...q, previousPrice: q.price, price: next, change: +(next - q.previousPrice).toFixed(2), changePct: +(((next - q.previousPrice) / q.previousPrice) * 100).toFixed(3), updatedAt: Date.now() };
    })), 1000);
    return () => window.clearInterval(id);
  }, []);

  const nifty = quotes.find(q => q.symbol === activeSymbol) ?? quotes[0];
  const advancing = quotes.filter(q => q.change >= 0).length;
  const declining = quotes.length - advancing;

  return <div className="grid min-h-full grid-cols-12 grid-rows-[minmax(0,1fr)_220px] gap-3">
    <Panel className="col-span-12 min-h-[540px] xl:col-span-4" title="Watchlist" action={<Settings className="h-4 w-4" />}>
      <div className="flex h-9 items-end gap-5 border-b border-[#21262D] px-3">
        {['My Watchlist', 'Favourites', 'Indices', 'Sector'].map((x, i) => <button key={x} className={`pb-2 text-xs ${i === 0 ? 'border-b-2 border-[#2EA043] text-[#2EA043]' : 'text-[#8B949E]'}`}>{x}</button>)}
      </div>
      <div className="grid grid-cols-[28px_minmax(120px,1.4fr)_1fr_1fr_.8fr] border-b border-[#21262D] px-3 py-2 text-[11px] font-medium text-[#8B949E]"><span/><span>SYMBOL</span><span className="text-right">LAST</span><span className="text-right">CHANGE</span><span className="text-right">VOL</span></div>
      {quotes.map(q => <QuoteRow key={q.symbol} q={q} flash={flashes[q.symbol]} active={q.symbol === activeSymbol} onClick={() => setActiveSymbol(q.symbol)} />)}
      <div className="flex items-center justify-between border-t border-[#21262D] px-3 py-2 text-[10px] text-[#8B949E]"><span>8 instruments</span><span className="num">A {advancing} · D {declining}</span></div>
    </Panel>

    <Panel className="col-span-12 min-h-[540px] xl:col-span-8" title={`${activeSymbol} · NSE · 1m`} action={<div className="flex gap-1"><button className="p-1 text-[#8B949E] hover:text-white"><Maximize2 className="h-4 w-4" /></button><button className="p-1 text-[#8B949E] hover:text-white"><MoreHorizontal className="h-4 w-4" /></button></div>}>
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex items-center justify-between border-b border-[#21262D] px-3 py-2">
          <div><div className="text-lg font-semibold">{activeSymbol}</div><div className={`num mt-0.5 text-xs ${nifty.change >= 0 ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>{fmt(nifty.price)} {nifty.change >= 0 ? '+' : ''}{fmt(nifty.change)} ({nifty.changePct >= 0 ? '+' : ''}{nifty.changePct.toFixed(2)}%)</div></div>
          <div className="flex items-center gap-1 text-xs">{['1m','5m','15m','1H','4H','1D'].map((x,i)=><button key={x} className={`px-2 py-1 ${i === 0 ? 'border-b border-[#2EA043] text-[#2EA043]' : 'text-[#8B949E]'}`}>{x}</button>)}</div>
        </div>
        <div className="min-h-0 flex-1 p-3"><CandleChart data={candles} /></div>
        <div className="flex items-center gap-4 border-t border-[#21262D] px-3 py-2 text-[10px] text-[#8B949E]"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#2EA043]"/>EMA 20</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#8B949E]"/>VWAP</span><span className="flex items-center gap-1"><Crosshair className="h-3 w-3"/>Crosshair ON</span><span className="ml-auto num">VOL {(nifty.volume / 1e6).toFixed(2)}M</span></div>
      </div>
    </Panel>

    <Panel className="col-span-12" title="Positions · Intraday" action={<button className="text-[#8B949E] hover:text-white"><MoreHorizontal className="h-4 w-4" /></button>}>
      <PositionTable />
    </Panel>

    <Panel className="col-span-12 xl:col-span-8" title="Market News" action={<button className="text-[10px] text-[#2EA043]">VIEW ALL</button>}>
      <div className="grid gap-1 md:grid-cols-2">{marketNews.map(([time, text]) => <div key={time} className="flex min-w-0 items-start gap-3 border-b border-[#21262D] px-3 py-2 last:border-0"><span className="num shrink-0 text-[10px] text-[#8B949E]">{time}</span><span className="text-xs leading-5"><i className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-[#2EA043] align-middle"/>{text}</span></div>)}</div>
    </Panel>
    <Panel className="col-span-12 xl:col-span-4" title="Market Breadth">
      <Breadth advancing={advancing} declining={declining} />
    </Panel>
  </div>;
}

function QuoteRow({ q, flash, active, onClick }: { q: Quote; flash?: 'up'|'down'; active: boolean; onClick: () => void }) {
  const positive = q.change >= 0;
  return <button onClick={onClick} className={`grid w-full grid-cols-[28px_minmax(120px,1.4fr)_1fr_1fr_.8fr] items-center border-b border-[#21262D] px-3 py-3 text-left hover:bg-[#1c2229] ${active ? 'bg-[#1a211d]' : ''}`}>
    <Star className="h-4 w-4 text-[#8B949E]" />
    <div><div className="text-[13px] font-medium">{q.symbol}</div><div className="text-[10px] text-[#8B949E]">{q.exchange}</div></div>
    <div className={`num rounded px-1 text-right text-[13px] font-medium ${positive ? 'text-[#2EA043]' : 'text-[#F85149]'} ${flash === 'up' ? 'flash-up' : flash === 'down' ? 'flash-down' : ''}`}>{fmt(q.price)}</div>
    <div className={`num text-right text-[12px] ${positive ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>{positive ? '+' : ''}{q.change.toFixed(2)} <span className="text-[10px]">({positive ? '+' : ''}{q.changePct.toFixed(2)}%)</span></div>
    <div className="num text-right text-[11px] text-[#8B949E]">{(q.volume / 1e6).toFixed(1)}M</div>
  </button>;
}

function CandleChart({ data }: { data: Candle[] }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; index: number } | null>(null);
  const width = 1000, height = 430, pad = { l: 14, r: 68, t: 46, b: 30 };
  const min = Math.min(...data.map(d => d.low));
  const max = Math.max(...data.map(d => d.high));
  const range = Math.max(1, max - min);
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const step = plotW / data.length;
  const bodyW = Math.max(4, step * 0.58);
  const x = (i: number) => pad.l + i * step + step / 2;
  const y = (v: number) => pad.t + ((max - v) / range) * plotH;
  const selected = hover ? data[hover.index] : data[data.length - 1];
  const selectedUp = selected.close >= selected.open;
  const selectedColor = selectedUp ? '#2EA043' : '#F85149';

  const yTicks = useMemo(() => Array.from({ length: 7 }, (_, i) => max - (range * i) / 6), [max, range]);
  const xLabels = useMemo(() => data.filter((_, i) => i % Math.max(1, Math.floor(data.length / 8)) === 0), [data]);

  function handleMove(event: PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const svgX = ((event.clientX - rect.left) / rect.width) * width;
    const svgY = ((event.clientY - rect.top) / rect.height) * height;
    if (svgX < pad.l || svgX > width - pad.r || svgY < pad.t || svgY > height - pad.b) return;
    const index = Math.max(0, Math.min(data.length - 1, Math.floor((svgX - pad.l) / step)));
    setHover({ x: x(index), y: svgY, index });
  }

  return <div className="relative h-full min-h-[350px] w-full overflow-hidden rounded-sm border border-[#21262D] bg-[#0d1117]">
    <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} className="h-full w-full touch-none" role="img" aria-label="Interactive one minute candlestick chart with crosshair and OHLC values" onPointerMove={handleMove} onPointerLeave={() => setHover(null)}>
      <g stroke="#21262D" strokeWidth="1">
        {yTicks.map((value, i) => <line key={`h-${i}`} x1={pad.l} x2={width - pad.r} y1={y(value)} y2={y(value)} />)}
        {Array.from({ length: 9 }, (_, i) => <line key={`v-${i}`} x1={pad.l + i * plotW / 8} x2={pad.l + i * plotW / 8} y1={pad.t} y2={height - pad.b} />)}
      </g>

      <g className="num" fontSize="9" fill="#8B949E">
        {yTicks.map((value, i) => <text key={i} x={width - pad.r + 8} y={y(value) + 3}>{fmt(value)}</text>)}
      </g>

      {data.map((d, i) => {
        const up = d.close >= d.open;
        const color = up ? '#2EA043' : '#F85149';
        const cx = x(i);
        const top = Math.min(y(d.open), y(d.close));
        const body = Math.max(2, Math.abs(y(d.close) - y(d.open)));
        return <g key={`${d.time}-${i}`}>
          <line x1={cx} x2={cx} y1={y(d.high)} y2={y(d.low)} stroke={color} strokeWidth="1.2" />
          <rect x={cx - bodyW / 2} y={top} width={bodyW} height={body} fill={color} />
        </g>;
      })}

      {xLabels.map((d) => {
        const i = data.indexOf(d);
        return <text key={d.time} x={x(i)} y={height - 10} textAnchor="middle" fill="#8B949E" fontSize="9" className="num">{d.time}</text>;
      })}

      <g>
        <rect x={pad.l + 8} y={8} width="300" height="25" rx="2" fill="#161B22" stroke="#21262D" />
        <text x={pad.l + 16} y="18" fill="#8B949E" fontSize="8">O</text><text x={pad.l + 28} y="20" fill="#fff" fontSize="10" className="num">{fmt(selected.open)}</text>
        <text x={pad.l + 94} y="18" fill="#8B949E" fontSize="8">H</text><text x={pad.l + 106} y="20" fill="#fff" fontSize="10" className="num">{fmt(selected.high)}</text>
        <text x={pad.l + 164} y="18" fill="#8B949E" fontSize="8">L</text><text x={pad.l + 176} y="20" fill="#fff" fontSize="10" className="num">{fmt(selected.low)}</text>
        <text x={pad.l + 234} y="18" fill="#8B949E" fontSize="8">C</text><text x={pad.l + 246} y="20" fill={selectedColor} fontSize="10" className="num">{fmt(selected.close)}</text>
      </g>

      {hover && <g pointerEvents="none">
        <line x1={hover.x} x2={hover.x} y1={pad.t} y2={height - pad.b} stroke="#8B949E" strokeWidth="1" strokeDasharray="3 3" />
        <line x1={pad.l} x2={width - pad.r} y1={hover.y} y2={hover.y} stroke="#8B949E" strokeWidth="1" strokeDasharray="3 3" />
        <rect x={Math.min(width - 62, Math.max(pad.l, hover.x - 30))} y={hover.y - 9} width="54" height="18" rx="2" fill="#161B22" stroke="#8B949E" />
        <text x={Math.min(width - 35, Math.max(pad.l + 27, hover.x - 3))} y={hover.y + 3} textAnchor="middle" fill="#fff" fontSize="9" className="num">{fmt(max - ((hover.y - pad.t) / plotH) * range)}</text>
        <rect x={Math.max(pad.l, Math.min(width - pad.r - 52, hover.x - 26))} y={height - pad.b + 5} width="52" height="18" rx="2" fill="#161B22" stroke="#8B949E" />
        <text x={Math.max(pad.l + 26, Math.min(width - pad.r - 26, hover.x))} y={height - pad.b + 17} textAnchor="middle" fill="#fff" fontSize="9">{selected.time}</text>
        <circle cx={hover.x} cy={y(selected.close)} r="3" fill={selectedColor} stroke="#fff" strokeWidth="1" />
      </g>}
    </svg>
    <div className="pointer-events-none absolute right-2 top-2 text-[9px] uppercase tracking-wider text-[#8B949E]">Move cursor · crosshair · OHLC</div>
  </div>;
}

function PositionTable() {
  return <div className="overflow-auto"><div className="grid min-w-[760px] grid-cols-[2fr_.6fr_.45fr_1fr_1fr_1fr_1fr] border-b border-[#21262D] px-3 py-2 text-[11px] text-[#8B949E]"><span>SYMBOL</span><span>SIDE</span><span>QTY</span><span>AVG PRICE</span><span>LTP</span><span>P&amp;L</span><span>P&amp;L %</span></div>{positions.map(p => <div key={p.symbol} className="grid min-w-[760px] grid-cols-[2fr_.6fr_.45fr_1fr_1fr_1fr_1fr] items-center px-3 py-2.5 text-xs hover:bg-[#1c2229]"><span>{p.symbol}</span><span className={p.side==='BUY'?'text-[#2EA043]':'text-[#F85149]'}>{p.side}</span><span className="num">{p.qty}</span><span className="num">{fmt(p.avgPrice)}</span><span className="num">{fmt(p.ltp)}</span><span className="num text-[#2EA043]">+{fmt(p.pnl)}</span><span className="num text-[#2EA043]">+{p.pnlPct.toFixed(2)}%</span></div>)}<div className="flex justify-end border-t border-[#21262D] px-3 py-2 text-xs"><span className="mr-4 text-[#8B949E]">Total P&amp;L</span><span className="num text-[#2EA043]">+5,171.25&nbsp;&nbsp; +2.15%</span></div></div>;
}

function Breadth({ advancing, declining }: { advancing: number; declining: number }) {
  const total = advancing + declining; const a = total ? advancing / total * 100 : 0;
  return <div className="p-3"><div className="mb-3 flex items-end justify-between"><div><div className="num text-2xl font-medium">{advancing + 38}</div><div className="text-[10px] uppercase tracking-wider text-[#8B949E]">Advancing</div></div><div className="text-right"><div className="num text-2xl font-medium text-[#F85149]">{declining + 12}</div><div className="text-[10px] uppercase tracking-wider text-[#8B949E]">Declining</div></div></div><div className="h-2 overflow-hidden rounded-sm bg-[#F85149]"><div className="h-full bg-[#2EA043]" style={{ width: `${Math.max(20, a)}%` }} /></div><div className="mt-3 flex justify-between text-[10px] text-[#8B949E]"><span>52W High 18</span><span>52W Low 4</span></div><div className="mt-3 flex items-center gap-2 text-xs"><BarChart3 className="h-4 w-4 text-[#8B949E]"/>Strong positive breadth</div></div>;
}
