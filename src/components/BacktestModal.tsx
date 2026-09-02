import { useEffect, useState } from 'react';
import { X, Loader2, CheckCircle2, Play } from 'lucide-react';

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

type Phase = 'setup' | 'running' | 'done';

const money = (v: number) =>
  `${v >= 0 ? '+' : ''}₹ ${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

const todayStr = () => new Date().toISOString().slice(0, 10);
const daysAgoStr = (n: number) => new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

/** From/To validation, in one place so it's easy to extend when more filters are added. */
function validateRange(from: string, to: string): string | null {
  if (!from || !to) return 'Both From and To dates are required.';
  const today = todayStr();
  if (from > today) return 'From date cannot be later than today.';
  if (to > today) return 'To date cannot be later than today.';
  if (from > to) return 'From date must be on or before To date.';
  return null;
}

export function BacktestModal({
  strategyId,
  strategyName,
  onClose,
  onComplete,
}: {
  strategyId: string;
  strategyName: string;
  onClose: () => void;
  onComplete: () => void;
}) {
  const [phase, setPhase] = useState<Phase>('setup');

  // Filters -- defaults to last 6 months, but nothing runs until the user hits Play.
  const [fromDate, setFromDate] = useState(daysAgoStr(180));
  const [toDate, setToDate] = useState(todayStr());
  const [validationError, setValidationError] = useState<string | null>(null);

  // Streaming state -- only populated once the user starts a run.
  const [runRange, setRunRange] = useState<{ start: string; end: string } | null>(null);
  const [trades, setTrades] = useState<TradeEvent[]>([]);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    if (!runRange) return; // setup phase -- nothing to stream yet

    const url = `${API_BASE}/api/strategies/${strategyId}/backtest/stream?start=${runRange.start}&end=${runRange.end}`;
    const es = new EventSource(url);

    es.addEventListener('trade', (e) => {
      const payload: TradeEvent = JSON.parse((e as MessageEvent).data);
      setTrades((prev) => [...prev, payload]);
    });

    es.addEventListener('done', (e) => {
      const payload: DoneEvent = JSON.parse((e as MessageEvent).data);
      setDone(payload);
      setPhase('done');
      es.close();
      onComplete(); // refresh the strategy cards behind the modal
    });

    es.onerror = () => {
      setStreamError('Lost connection to the backtest stream. Is the backend still running?');
      es.close();
    };

    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRange]);

  const handlePlay = () => {
    const err = validateRange(fromDate, toDate);
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);
    setStreamError(null);
    setTrades([]);
    setDone(null);
    setPhase('running');
    setRunRange({ start: fromDate, end: toDate });
  };

  const handleRunAnother = () => {
    setPhase('setup');
    setRunRange(null);
    setTrades([]);
    setDone(null);
  };

  const last = trades[trades.length - 1];
  const liveCount = done?.total_trades ?? last?.running_trade_count ?? 0;
  const livePnl = done?.total_pnl ?? last?.running_pnl ?? 0;
  const liveWinRate = done?.win_rate ?? last?.running_win_rate ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col border border-[#30363D] bg-[#0D1117]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#21262D] px-4 py-3">
          <div className="text-sm font-semibold">{strategyName} — Backtest</div>
          <button onClick={onClose} className="text-[#8B949E] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* SETUP: date filters, nothing runs until Play is clicked */}
        {phase === 'setup' && (
          <div className="p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">From Date</label>
                <input
                  type="date"
                  value={fromDate}
                  max={todayStr()}
                  onChange={(e) => {
                    setFromDate(e.target.value);
                    setValidationError(null);
                  }}
                  className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">To Date</label>
                <input
                  type="date"
                  value={toDate}
                  min={fromDate}
                  max={todayStr()}
                  onChange={(e) => {
                    setToDate(e.target.value);
                    setValidationError(null);
                  }}
                  className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]"
                />
              </div>
            </div>

            <div className="mt-3 text-[10px] text-[#8B949E]">More filters (margin per lot, target/stop %) are coming soon.</div>

            {validationError && <div className="mt-3 text-xs text-[#F85149]">{validationError}</div>}

            <div className="mt-5 flex justify-end gap-2">
              <button onClick={onClose} className="h-8 border border-[#30363D] px-4 text-xs hover:bg-[#21262D]">
                Cancel
              </button>
              <button
                onClick={handlePlay}
                className="flex h-8 items-center gap-2 bg-[#2EA043] px-4 text-xs font-semibold hover:bg-[#2c9a3f]"
              >
                <Play className="h-3.5 w-3.5" />
                Run Backtest
              </button>
            </div>
          </div>
        )}

        {/* RUNNING / DONE: live stats + trade grid */}
        {phase !== 'setup' && (
          <>
            <div className="border-b border-[#21262D] px-4 py-2 text-[10px] text-[#8B949E]">
              {runRange?.start} → {runRange?.end}
            </div>

            {streamError && <div className="border-b border-[#21262D] p-3 text-xs text-[#F85149]">{streamError}</div>}

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

            <div className="flex items-center gap-2 border-b border-[#21262D] px-4 py-2 text-xs text-[#8B949E]">
              {phase === 'done' ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-[#2EA043]" />
                  Backtest complete — {done?.total_trades} trades processed.
                </>
              ) : (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Running backtest — trades appear below as they're computed…
                </>
              )}
            </div>

            <div className="flex-1 overflow-auto">
              <div className="min-w-[720px]">
                <div className="grid grid-cols-[150px_150px_1fr_110px_100px] border-b border-[#21262D] bg-[#0D1117] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-[#8B949E]">
                  <span>Trade Start</span>
                  <span>Trade End</span>
                  <span>Legs</span>
                  <span>Exit Reason</span>
                  <span className="text-right">P&L</span>
                </div>
                {trades.length === 0 && phase === 'running' && (
                  <div className="p-4 text-xs text-[#8B949E]">Waiting for the first trade…</div>
                )}
                {trades.length === 0 && phase === 'done' && (
                  <div className="p-4 text-xs text-[#8B949E]">No trades were generated for this window.</div>
                )}
                {trades.map((t, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[150px_150px_1fr_110px_100px] items-center border-b border-[#21262D] px-3 py-2.5 text-xs hover:bg-[#1c2229]"
                  >
                    <span className="num">{dateTime(t.entry_time)}</span>
                    <span className="num">{dateTime(t.exit_time)}</span>
                    <span className="truncate pr-2 text-[#8B949E]" title={t.legs.join(', ')}>
                      {t.legs.join(', ')}
                    </span>
                    <span className="text-[10px] text-[#8B949E]">{t.exit_reason}</span>
                    <span className={`num text-right ${t.pnl >= 0 ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>
                      {money(t.pnl)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-[#21262D] p-3">
              {phase === 'done' && (
                <button onClick={handleRunAnother} className="h-8 border border-[#30363D] px-4 text-xs hover:bg-[#21262D]">
                  Run Another
                </button>
              )}
              <button onClick={onClose} className="h-8 border border-[#30363D] px-4 text-xs hover:bg-[#21262D]">
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
