import { useEffect, useState } from 'react';
import { X, Loader2, CheckCircle2, Play, Download } from 'lucide-react';
import * as XLSX from 'xlsx';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

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
  reference_atm?: number;
  details?: { spot?: number; fills?: { ts: string; action: string; option_type: string; lots: number; price: number; tag: string }[] };
};

type DoneEvent = {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
};

type BacktestErrorEvent = {
  error: string;
  strategy_id: string;
};

type Phase = 'setup' | 'running' | 'done';

type NiftyFilters = {
  entryTime: string;
  indiaVixBelow: string;
  combinedPremium: string;
  only100s: boolean;
  forceAt1501: boolean;
  // Optional (blank = unset): forced-entry above this is skipped rather
  // than taken, and the hard stop scales as this fraction of the entry
  // premium instead of the fixed absolute default.
  maxForcedEntryPremium: string;
  hardStopPct: string;
};

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

// V6: was (9 * 60 + 16) -- excluded the actual 09:15 market open used by
// V2/V3/V4, so that starting point could never be selected in the UI.
const entryTimes = Array.from({ length: (15 * 60 + 1) - (9 * 60 + 15) + 1 }, (_, index) => {
  const totalMinutes = 9 * 60 + 15 + index;
  return `${String(Math.floor(totalMinutes / 60)).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`;
}).filter((value) => value <= '15:01');

function exportTrades(strategyName: string, range: { start: string; end: string }, trades: TradeEvent[], totalPnl: number) {
  const rows: unknown[][] = [
    ['Profit Pilot'],
    ['Strategy Name', strategyName],
    ['Backtest Period', `${range.start} to ${range.end}`],
    ['Export Date', new Date()],
    ['Total Trades', trades.length],
    ['Aggregated Profit/Loss', totalPnl],
    [],
    ['S.No', 'Trade Date', 'Time', 'Symbol', 'Action', 'Lots', 'Price', 'NIFTY Spot', 'Stage', 'P&L'],
  ];
  let serial = 1;
  trades.forEach((trade) => {
    const fills = trade.details?.fills ?? [];
    if (!fills.length) {
      rows.push([serial++, trade.entry_time.slice(0, 10), new Date(trade.entry_time), trade.legs.join(', '), 'TRADE', '', '', trade.details?.spot ?? '', '', trade.pnl]);
      return;
    }
    fills.forEach((fill, index) => rows.push([
      serial++, fill.ts.slice(0, 10), new Date(fill.ts).toLocaleString('en-IN'), `${trade.reference_atm ?? ''} ${fill.option_type}`,
      fill.action, fill.lots, fill.price, index === 0 && fill.tag === 'INITIAL' ? (trade.details?.spot ?? '') : '', fill.tag, index === fills.length - 1 ? trade.pnl : '',
    ]));
  });
  const worksheet = XLSX.utils.aoa_to_sheet(rows);
  worksheet['!cols'] = [8, 14, 22, 18, 10, 8, 12, 14, 18, 14].map((wch) => ({ wch }));
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Trade Details');
  XLSX.writeFile(workbook, `Profit-Pilot-${strategyName.replace(/[^a-z0-9]+/gi, '-')}-${range.start}-to-${range.end}.xlsx`);
}

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
  const [filters, setFilters] = useState<NiftyFilters>({
    // V6: was '15:01' -- that default meant the strategy only ever scanned
    // the last 34 minutes of the day unless a user manually changed this.
    entryTime: '09:15',
    indiaVixBelow: '15',
    combinedPremium: '50',
    only100s: true,
    forceAt1501: false,
    maxForcedEntryPremium: '',
    hardStopPct: '',
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  // Streaming state -- only populated once the user starts a run.
  const [runRange, setRunRange] = useState<{ start: string; end: string; filters: NiftyFilters } | null>(null);
  const [trades, setTrades] = useState<TradeEvent[]>([]);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    if (!runRange) return; // setup phase -- nothing to stream yet

    const params = new URLSearchParams({
      start: runRange.start,
      end: runRange.end,
      entryTime: runRange.filters.entryTime,
      indiaVixBelow: runRange.filters.indiaVixBelow,
      combinedPremium: runRange.filters.combinedPremium,
      only100s: String(runRange.filters.only100s),
      forceAt1501: String(runRange.filters.forceAt1501),
    });
    // Optional advanced filters -- only sent when the user actually set them,
    // so leaving them blank preserves the same behavior as before they existed.
    if (runRange.filters.maxForcedEntryPremium.trim() !== '') {
      params.set('maxForcedEntryPremium', runRange.filters.maxForcedEntryPremium);
    }
    if (runRange.filters.hardStopPct.trim() !== '') {
      params.set('hardStopPct', runRange.filters.hardStopPct);
    }
    const url = `${API_BASE}/strategies/${strategyId}/backtest/stream?${params.toString()}`;
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

    // The backend emits this named event (instead of just dropping the
    // connection) when the backtest itself throws -- e.g. a missing DB
    // table or a bad data assumption. Without this listener the modal
    // would sit on "Running..." forever, since a named SSE event doesn't
    // trigger EventSource's onerror.
    es.addEventListener('backtest_error', (e) => {
      const payload: BacktestErrorEvent = JSON.parse((e as MessageEvent).data);
      setStreamError(`Backtest failed: ${payload.error}`);
      setPhase('done');
      es.close();
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
    const vix = Number(filters.indiaVixBelow);
    const premium = Number(filters.combinedPremium);
    if (!Number.isFinite(vix) || vix <= 0 || !Number.isFinite(premium) || premium < 0) {
      setValidationError('VIX must be positive and combined premium cannot be negative.');
      return;
    }
    if (filters.maxForcedEntryPremium.trim() !== '') {
      const cap = Number(filters.maxForcedEntryPremium);
      if (!Number.isFinite(cap) || cap <= 0) {
        setValidationError('Max forced-entry premium must be a positive number, or left blank for uncapped.');
        return;
      }
    }
    if (filters.hardStopPct.trim() !== '') {
      const pct = Number(filters.hardStopPct);
      if (!Number.isFinite(pct) || pct <= 0 || pct > 1) {
        setValidationError('Hard stop % must be between 0 and 1 (e.g. 0.16 for 16%), or left blank for the fixed default.');
        return;
      }
    }
    setPhase('running');
    setRunRange({ start: fromDate, end: toDate, filters: { ...filters } });
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

            {strategyId === 'nifty-atm-straddle' && (
              <div className="mt-4 grid gap-4 border-t border-[#21262D] pt-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">Entry Time After</label>
                  <select value={filters.entryTime} onChange={(e) => setFilters((current) => ({ ...current, entryTime: e.target.value }))} className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]">
                    {entryTimes.map((entryTime) => <option key={entryTime} value={entryTime}>{entryTime}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">India VIX Below</label>
                  <input type="number" min="0.01" step="0.01" value={filters.indiaVixBelow} onChange={(e) => setFilters((current) => ({ ...current, indiaVixBelow: e.target.value }))} className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]" />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">Combined Premium</label>
                  <input type="number" min="0" step="0.01" value={filters.combinedPremium} onChange={(e) => setFilters((current) => ({ ...current, combinedPremium: e.target.value }))} className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]" />
                </div>
                <label className="flex items-center gap-2 self-end text-xs text-[#C9D1D9]">
                  <input type="checkbox" checked={filters.only100s} onChange={(e) => setFilters((current) => ({ ...current, only100s: e.target.checked }))} className="h-4 w-4 accent-[#2EA043]" />
                  Only 100's strikes
                </label>
                <label className="flex items-center gap-2 text-xs text-[#C9D1D9] sm:col-span-2">
                  <input type="checkbox" checked={filters.forceAt1501} onChange={(e) => setFilters((current) => ({ ...current, forceAt1501: e.target.checked }))} className="h-4 w-4 accent-[#D29922]" />
                  3PM is my price — force entry at 15:01 if no earlier trade exists
                </label>
                <div>
                  <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">Max Forced-Entry Premium (optional)</label>
                  <input
                    type="number" min="0.01" step="0.01" placeholder="Uncapped"
                    value={filters.maxForcedEntryPremium}
                    onChange={(e) => setFilters((current) => ({ ...current, maxForcedEntryPremium: e.target.value }))}
                    className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] uppercase tracking-wider text-[#8B949E]">Hard Stop % of Entry (optional)</label>
                  <input
                    type="number" min="0.01" max="1" step="0.01" placeholder="Fixed default"
                    value={filters.hardStopPct}
                    onChange={(e) => setFilters((current) => ({ ...current, hardStopPct: e.target.value }))}
                    className="h-9 w-full border border-[#30363D] bg-[#161B22] px-3 text-xs outline-none focus:border-[#2EA043]"
                  />
                </div>
              </div>
            )}

            <div className="mt-3 text-[10px] text-[#8B949E]">Entry filters apply only to the NIFTY ATM Straddle. All averaging, target, stop-loss, and exit rules remain unchanged unless overridden by the optional filters above.</div>

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
            <div className="flex items-center justify-between border-b border-[#21262D] px-4 py-2 text-[10px] text-[#8B949E]">
              <span>{runRange?.start} → {runRange?.end}</span>
              {phase === 'done' && trades.length > 0 && runRange && (
                <button onClick={() => exportTrades(strategyName, runRange, trades, livePnl)} title="Export trade details to Excel" aria-label="Export trade details to Excel" className="p-1 hover:bg-[#21262D] hover:text-white">
                  <Download className="h-4 w-4" />
                </button>
              )}
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
                  {streamError ? (
                    <span className="text-[#F85149]">Backtest stopped due to an error.</span>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5 text-[#2EA043]" />
                      Backtest complete — {done?.total_trades} trades processed.
                    </>
                  )}
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
                {trades.length === 0 && phase === 'done' && !streamError && (
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
