import { useState } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { Footer } from './Footer';
import type { ReactNode } from 'react';
export function TerminalLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  return <div className="min-h-screen bg-[#0D1117] text-white"><Header/><Sidebar collapsed={collapsed} onToggle={() => setCollapsed(v => !v)}/><div className={`pt-12 pb-6 transition-[padding] duration-200 ${collapsed ? 'pl-12' : 'pl-[200px]'}`}><main className="min-h-[calc(100vh-72px)] overflow-y-auto p-3">{children}</main></div><Footer/></div>;
}
