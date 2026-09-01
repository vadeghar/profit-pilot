import { useMemo, useState } from 'react';
import { Panel } from '../components/Panel';
import { placeOrder, useWebSocket } from '../context/WebSocketContext';
import type { Side } from '../types/market';

export function OrderTicketView() {
  const { send, status } = useWebSocket();
  const [side, setSide] = useState<Side>('BUY');
  const [symbol, setSymbol] = useState('NIFTY 50');
  const [price, setPrice] = useState('24833.15');
  const [volume, setVolume] = useState('75');
  const [message, setMessage] = useState('');
  const total = useMemo(() => Number(price || 0) * Number(volume || 0), [price, volume]);

  const submit = () => {
    const sidePrice = Number(price), qty = Number(volume);
    if (!symbol.trim() || !Number.isFinite(sidePrice) || sidePrice <= 0 || !Number.isInteger(qty) || qty <= 0) {
      setMessage('Enter a valid symbol, price and integer quantity.'); return;
    }
    const ok = placeOrder(send, { symbol: symbol.trim(), side, sidePrice, volume: qty });
    setMessage(ok ? `ORDER_PLACEMENT sent: ${side} ${qty} ${symbol}` : 'WebSocket is not connected. Order not sent.');
  };

  return <div className="grid max-w-3xl grid-cols-[minmax(0,1fr)_300px] gap-3"><Panel title="Instant Order Ticket"><div className="p-4">
    <div className="mb-4 grid grid-cols-2 gap-1 bg-[#0D1117] p-1"><button onClick={() => setSide('BUY')} className={`h-10 text-sm font-semibold ${side === 'BUY' ? 'bg-[#2EA043] text-white' : 'text-[#8B949E]'}`}>BUY</button><button onClick={() => setSide('SELL')} className={`h-10 text-sm font-semibold ${side === 'SELL' ? 'bg-[#F85149] text-white' : 'text-[#8B949E]'}`}>SELL</button></div>
    <label className="mb-1 block text-[11px] uppercase tracking-wider text-[#8B949E]">Symbol</label><input value={symbol} onChange={e=>setSymbol(e.target.value)} className="mb-4 h-9 w-full border border-[#30363D] bg-[#0D1117] px-3 text-xs outline-none focus:border-[#2EA043]" />
    <div className="grid grid-cols-2 gap-3"><div><label className="mb-1 block text-[11px] uppercase tracking-wider text-[#8B949E]">Limit Price</label><input type="number" value={price} onChange={e=>setPrice(e.target.value)} className="num h-9 w-full border border-[#30363D] bg-[#0D1117] px-3 text-right outline-none focus:border-[#2EA043]" /></div><div><label className="mb-1 block text-[11px] uppercase tracking-wider text-[#8B949E]">Quantity</label><input type="number" value={volume} onChange={e=>setVolume(e.target.value)} className="num h-9 w-full border border-[#30363D] bg-[#0D1117] px-3 text-right outline-none focus:border-[#2EA043]" /></div></div>
    <div className="mt-4 flex justify-between border-t border-[#21262D] pt-3 text-xs text-[#8B949E]"><span>Estimated Value</span><span className="num text-white">₹ {total.toLocaleString('en-IN', {minimumFractionDigits:2})}</span></div>
    <button disabled={status !== 'OPEN'} onClick={submit} className={`mt-4 h-10 w-full font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${side === 'BUY' ? 'bg-[#2EA043]' : 'bg-[#F85149]'}`}>PLACE {side} ORDER</button>
    {message && <div className="mt-3 border border-[#21262D] bg-[#0D1117] p-3 text-xs text-[#8B949E]">{message}</div>}
  </div></Panel><Panel title="Wire Contract"><pre className="overflow-auto p-4 text-[11px] leading-5 text-[#8B949E]">{JSON.stringify({type:'ORDER_PLACEMENT',symbol,side,sidePrice:Number(price),volume:Number(volume)}, null, 2)}</pre></Panel></div>;
}
