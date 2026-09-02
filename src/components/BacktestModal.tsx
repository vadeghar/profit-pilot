import { useEffect, useRef, useState } from 'react';
import { X, Loader2, CheckCircle2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

type TradeEvent = {
  entry_time: string;
  exit_time: string;
  legs: string[];
  exit_reason: string;
  pnl: number;
  pnl_pct: number;
  running_trade_count: number;
  running_pnl: number;
  running_win_rate: number;
};

type DoneEvent = {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
};

const money = (v: number) =>
  `${v >= 0 ? '+' : ''}₹ ${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

export function BacktestModal({
  strategyId,
  strategyName,
  start,
  end,
  onClose,
  onComplete,
}: {
  strategyId: string;
  strategyName: string;
  start: string;
  end: string;
  onClose: () => void;
  onComplete: () => void;
}) {
  const [trades, setTrades] = useState<TradeEvent[]>([]);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tableEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const url = `${API_BASE}/api/strategies/${strategyId}/backtest/stream?start=${start}&end=${end}`;
    const es = new EventSource(url);

    es.addEventListener('trade', (e) => {
      const payload: TradeEvent = JSON.parse((e as MessageEvent).data);
      setTrades((prev) => [...prev, payload]);
    });

    es.addEventListener('done', (e) => {
      const payload: DoneEvent = JSON.parse((e as MessageEvent).data);
      setDone(payload);
      es.close();
      onComplete(); // refresh the strategy cards behind the modal
    });

    es.onerror = () => {
      setError('Lost connection to the backtest stream. Is the backend still running?');
      es.close();
    };

    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId, start, end]);

  useEffect(() => {
    tableEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [trades.length]);

  const last = trades[trades.length - 1];
  const liveCount = done?.total_trades ?? last?.running_trade_count ?? 0;
  const livePnl = done?.total_pnl ?? last?.running_pnl ?? 0;
  const liveWinRate = done?.win_rate ?? last?.running_win_rate ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col border border-[#30363D] bg-[#0D1117]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#21262D] px-4 py-3">
          <div>
            <div className="text-sm font-semibold">{strategyName} — Backtest</div>
            <div className="mt-0.5 text-[10px] text-[#8B949E]">
              {start} → {end}
            </div>
          </div>
          <button onClick={onClose} className="text-[#8B949E] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && <div className="border-b border-[#21262D] p-3 text-xs text-[#F85149]">{error}</div>}

        {/* Live stats */}
        <div className="grid grid-cols-3 gap-px border-b border-[#21262D] bg-[#21262D]">
          <div className="bg-[#161B22] px-4 py-3">
            <div className="text-[10px] uppercase tracking-wider text-[#8B949E]">No. of Trades</div>
            <div className="num mt-1 text-lg">{liveCount}</div>
          </div>
          <div className="bg-[#161B22] px-4 py-3">
            <div className="text-[10px] uppercase tracking-wider text-[#8B949E]">Total P&L</div>
            <div className={`num mt-1 text-lg ${livePnl >= 0 ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>
              {money(livePnl)}
            </div>
          </div>
          <div className="bg-[#161B22] px-4 py-3">
            <div className="text-[10px] uppercase tracking-wider text-[#8B949E]">Win Rate</div>
            <div className="num mt-1 text-lg">{liveWinRate.toFixed(1)}%</div>
          </div>
        </div>

        {/* Status line */}
        <div className="flex items-center gap-2 border-b border-[#21262D] px-4 py-2 text-xs text-[#8B949E]">
          {done ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-[#2EA043]" />
              Backtest complete — {done.total_trades} trades processed.
            </>
          ) : (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Running backtest — trades appear below as they're computed…
            </>
          )}
        </div>

        {/* Trade grid */}
        <div className="flex-1 overflow-auto">
          <div className="min-w-[640px]">
            <div className="grid grid-cols-[110px_1fr_110px_110px] border-b border-[#21262D] bg-[#0D1117] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-[#8B949E]">
              <span>Entry Date</span>
              <span>Legs</span>
              <span>Exit Reason</span>
              <span className="text-right">P&L</span>
            </div>
            {trades.length === 0 && !done && (
              <div className="p-4 text-xs text-[#8B949E]">Waiting for the first trade…</div>
            )}
            {trades.length === 0 && done && (
              <div className="p-4 text-xs text-[#8B949E]">No trades were generated for this window.</div>
            )}
            {trades.map((t, i) => (
              <div
                key={i}
                className="grid grid-cols-[110px_1fr_110px_110px] items-center border-b border-[#21262D] px-3 py-2.5 text-xs hover:bg-[#1c2229]"
              >
                <span className="num">{shortDate(t.entry_time)}</span>
                <span className="truncate pr-2 text-[#8B949E]" title={t.legs.join(', ')}>
                  {t.legs.join(', ')}
                </span>
                <span className="text-[10px] text-[#8B949E]">{t.exit_reason}</span>
                <span className={`num text-right ${t.pnl >= 0 ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>
                  {money(t.pnl)}
                </span>
              </div>
            ))}
            <div ref={tableEndRef} />
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#21262D] p-3 text-right">
          <button onClick={onClose} className="h-8 border border-[#30363D] px-4 text-xs hover:bg-[#21262D]">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
