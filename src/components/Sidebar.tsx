
import { Bell, BookOpen, BriefcaseBusiness, CandlestickChart, ChevronLeft, ChevronRight, History, LayoutDashboard, Newspaper, Settings, SlidersHorizontal, Target, WalletCards, BarChart3, Wrench, ShoppingCart, Layers3 } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const items = [
 ['/', 'Dashboard', LayoutDashboard],
 ['/watchlists', 'Watchlists', CandlestickChart],
 ['/order-books', 'Order Books', BookOpen],
 ['/portfolio', 'Portfolio', WalletCards],
 ['/positions', 'Positions', BriefcaseBusiness],
 ['/alerts', 'Alert Manager', Bell],
 ['/history', 'Trade History', History],
 ['/news', 'Market News', Newspaper],
 ['/analytics', 'Analytics', BarChart3],
 ['/strategy', 'Strategy Builder', Target],
 ['/tools', 'Tools', Wrench],
 ['/settings', 'Settings', Settings],
] as const;

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
 return <aside className={`fixed bottom-6 left-0 top-12 z-40 border-r border-[#21262D] bg-[#0D1117] transition-[width] duration-200 ${collapsed ? 'w-12' : 'w-[200px]'}`}>
  <div className="flex h-full flex-col">
   <button onClick={onToggle} className="flex h-10 items-center justify-end border-b border-[#21262D] px-3 text-[#8B949E] hover:text-white" aria-label="Toggle sidebar">{collapsed?<ChevronRight className="h-4 w-4"/>:<ChevronLeft className="h-4 w-4"/>}</button>
   <nav className="flex-1 overflow-auto py-2">{items.map(([path,label,Icon])=><NavLink key={label} to={path} title={collapsed?label:undefined} className={({isActive})=>`group relative flex h-9 items-center gap-3 border-l-2 px-3 text-[12px] ${isActive?'border-[#2EA043] bg-[#161B22] text-white':'border-transparent text-[#8B949E] hover:bg-[#161B22] hover:text-white'}`}><Icon className="h-4 w-4 shrink-0"/><span className={collapsed?'sr-only':''}>{label}</span></NavLink>)}</nav>
   <div className="border-t border-[#21262D] p-2"><button className="flex w-full items-center gap-3 px-1 py-2 text-[11px] uppercase tracking-wider text-[#8B949E]"><SlidersHorizontal className="h-4 w-4"/><span className={collapsed?'sr-only':''}>Workspace</span></button></div>
  </div>
 </aside>
}
