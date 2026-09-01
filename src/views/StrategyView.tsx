import { useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { Panel } from '../components/Panel';
import { DataWorkspace } from './MockWorkspaces';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

type StrategyCard = {
  id: string;
  name: string;
  subtitle: string;
  status: string;
  win_rate: number | null;
  pnl: number | null;
  trades: number;
};

const money = (v: number) => `${v >= 0 ? '+' : ''}₹ ${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function StrategyView() {
  const [strategies, setStrategies] = useState<StrategyCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  const loadStrategies = () => {
    fetch(`${API_BASE}/api/strategies`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then(setStrategies)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const runBacktest = async (id: string) => {
    setRunningId(id);
    try {
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - 1000 * 60 * 60 * 24 * 180).toISOString().slice(0, 10); // last ~6 months
      const res = await fetch(`${API_BASE}/api/strategies/${id}/backtest?start=${start}&end=${end}`);
      if (!res.ok) throw new Error(`Backtest failed: ${res.status}`);
      loadStrategies();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunningId(null);
    }
  };

  const stats: [string, string, string?][] = strategies
    ? [
        ['Strategies', String(strategies.length)],
        ['Live', String(strategies.filter((s) => s.status === 'LIVE').length)],
        ['Backtests Run', String(strategies.filter((s) => s.trades > 0).length)],
        [
          'Net Strategy P&L',
          money(strategies.reduce((sum, s) => sum + (s.pnl ?? 0), 0)),
        ],
      ]
    : [];

  return (
    <DataWorkspace title="Strategy Builder" subtitle="Backtest and deploy rule-based strategies" stats={stats}>
      {error && (
        <Panel title="Connection Error">
          <div className="p-4 text-xs text-[#F85149]">
            Couldn't reach the backend at {API_BASE}. Is `uvicorn api.main:app --reload` running? ({error})
          </div>
        </Panel>
      )}

      {!strategies && !error && (
        <Panel title="Loading">
          <div className="p-4 text-xs text-[#8B949E]">Loading strategies…</div>
        </Panel>
      )}

      {strategies && (
        <div className="grid gap-3 lg:grid-cols-3">
          {strategies.map((s) => (
            <Panel key={s.id} title={s.name}>
              <div className="p-4">
                <div className="text-xs text-[#8B949E]">{s.subtitle}</div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-[10px] font-semibold text-[#8B949E]">{s.status}</span>
                  <span className="num text-lg">{s.win_rate !== null ? `${s.win_rate}%` : '—'}</span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="border border-[#21262D] p-2">
                    <div className="text-[9px] text-[#8B949E]">P&L</div>
                    <div className={`num ${(s.pnl ?? 0) >= 0 ? 'text-[#2EA043]' : 'text-[#F85149]'}`}>
                      {s.pnl !== null ? money(s.pnl) : '—'}
                    </div>
                  </div>
                  <div className="border border-[#21262D] p-2">
                    <div className="text-[9px] text-[#8B949E]">TRADES</div>
                    <div className="num">{s.trades}</div>
                  </div>
                </div>
                <button
                  onClick={() => runBacktest(s.id)}
                  disabled={runningId === s.id}
                  className="mt-3 flex h-8 w-full items-center justify-center gap-2 border border-[#30363D] text-xs hover:bg-[#21262D] disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" />
                  {runningId === s.id ? 'Running…' : 'Run Backtest (6M)'}
                </button>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </DataWorkspace>
  );
}
