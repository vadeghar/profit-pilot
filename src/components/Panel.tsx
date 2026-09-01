import type { ReactNode } from 'react';
export function Panel({ title, action, children, className = '' }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel flex min-h-0 flex-col overflow-hidden ${className}`}>
    {title && <div className="flex h-9 shrink-0 items-center justify-between border-b border-[#21262D] px-3"><h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#8B949E]">{title}</h2>{action}</div>}
    <div className="min-h-0 flex-1">{children}</div>
  </section>;
}
