
import { Bell, ChevronDown, ChevronRight, HelpCircle, Search, UserCircle } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export function Header() {
 const [tradeOpen,setTradeOpen]=useState(false); const [derivativesOpen,setDerivativesOpen]=useState(false); const nav=useNavigate();
 const main=[['Markets','/'],['Trade',null],['Analytics','/analytics'],['Tools','/tools'],['Settings','/settings']] as const;
 return <header className="fixed inset-x-0 top-0 z-50 flex h-12 items-center border-b border-[#21262D] bg-[#0D1117] px-4">
  <Link to="/" className="w-[184px] shrink-0 text-base font-bold uppercase tracking-wider">PROFIT <span className="text-[#2EA043]">PILOT</span></Link>
  <div className="relative hidden w-[300px] shrink-0 md:block"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#8B949E]"/><input className="h-8 w-full border border-[#30363D] bg-[#161B22] pl-9 pr-3 text-xs text-white outline-none placeholder:text-[#8B949E] focus:border-[#2EA043]" placeholder="Search markets, symbols..."/></div>
  <nav className="ml-3 flex h-full items-center gap-1">
   {main.map(([item,path])=>item==='Trade'?<div key={item} className="relative h-full" onMouseLeave={()=>{setTradeOpen(false);setDerivativesOpen(false)}}><button onClick={()=>setTradeOpen(v=>!v)} className={`flex h-full items-center gap-1 px-3 text-[13px] font-medium ${tradeOpen?'text-[#2EA043]':'text-white hover:text-[#2EA043]'}`}>Trade <ChevronDown className="h-3 w-3"/></button>{tradeOpen&&<div className="absolute left-0 top-12 w-48 border border-[#30363D] bg-[#161B22] shadow-2xl">{[['Spot Trading','/trade/spot-trading'],['Derivatives',null],['Algorithmic Orders','/trade/algorithmic-orders']].map(([sub,path])=><div key={sub} className="relative" onMouseEnter={()=>setDerivativesOpen(sub==='Derivatives')}><button onClick={()=>path&&nav(path)} className={`flex h-10 w-full items-center justify-between px-4 text-left text-xs ${sub==='Derivatives'&&derivativesOpen?'bg-[#2EA043] text-white':'text-white hover:bg-[#21262D]'}`}>{sub}{sub==='Derivatives'&&<ChevronRight className="h-3 w-3"/>}</button>{sub==='Derivatives'&&derivativesOpen&&<div className="absolute left-full top-0 w-48 border border-[#30363D] bg-[#161B22] shadow-2xl">{[['Perpetuals','/trade/perpetuals'],['Options','/trade/options'],['Futures Contracts','/trade/futures']].map(([x,p])=><button onClick={()=>nav(p)} key={x} className="block h-10 w-full px-4 text-left text-xs text-white hover:bg-[#21262D]">{x}</button>)}</div>}</div>)}</div>}</div>
   :<Link key={item} to={path!} className="flex h-full items-center px-3 text-[13px] font-medium text-white hover:text-[#2EA043]">{item}</Link>)}
  </nav>
  <div className="ml-auto flex items-center gap-4"><Bell className="h-4 w-4 text-[#8B949E]"/><HelpCircle className="h-4 w-4 text-[#8B949E]"/><Link to="/settings" className="flex items-center gap-2 border-l border-[#21262D] pl-4 text-xs"><UserCircle className="h-6 w-6 text-[#8B949E]"/> Trader One <ChevronDown className="h-3 w-3"/></Link></div>
 </header>
}
