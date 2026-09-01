import { Activity, Wifi } from 'lucide-react';
import { useEffect, useState } from 'react';
export function Footer() {
  const [utc, setUtc] = useState(new Date().toISOString().slice(11,19));
  useEffect(() => { const id=setInterval(()=>setUtc(new Date().toISOString().slice(11,19)),1000); return ()=>clearInterval(id); },[]);
  const tape=['NIFTY 50  24,833.15 ▲ 142.60 (0.58%)','BANKNIFTY  50,212.45 ▲ 256.90 (0.51%)','SENSEX  81,210.25 ▲ 456.75 (0.57%)','USD/INR  83.21 ▼ -0.12 (-0.14%)','GOLD  71,245 ▲ 312 (0.44%)'];
  return <footer className="fixed bottom-0 left-0 right-0 z-50 flex h-6 border-t border-[#21262D] bg-[#0D1117] text-[10px]"><div className="flex min-w-0 flex-1 overflow-hidden"><div className="shrink-0 border-r border-[#21262D] px-3 py-1 font-medium uppercase tracking-wider text-[#2EA043]">Market Ticker</div><div className="overflow-hidden whitespace-nowrap"><div className="marquee flex min-w-max">{[...tape,...tape].map((x,i)=><span key={i} className="border-r border-[#21262D] px-4 py-1"><span className={x.includes('▼')?'text-[#F85149]':'text-[#8B949E]'}>{x}</span></span>)}</div></div></div><div className="flex shrink-0 items-center gap-2 border-l border-[#21262D] px-3"><Activity className="h-3 w-3 text-[#2EA043]"/><span className="text-[#8B949E]">UTC</span><span className="num">{utc}</span><Wifi className="ml-2 h-3 w-3 text-[#2EA043]"/></div></footer>;
}
