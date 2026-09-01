import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { MarketTick, OrderPlacement } from '../types/market';

type ConnectionState = 'CONNECTING' | 'OPEN' | 'CLOSED' | 'ERROR';
interface WebSocketContextValue {
  status: ConnectionState;
  latencyMs: number | null;
  lastMessageAt: number | null;
  send: (payload: unknown) => boolean;
  subscribe: (handler: (tick: MarketTick) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef(new Set<(tick: MarketTick) => void>());
  const pingSentAt = useRef<number | null>(null);
  const [status, setStatus] = useState<ConnectionState>('CONNECTING');
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);

  useEffect(() => {
    const url = import.meta.env.VITE_WS_URL;
    if (!url) {
      // UI-only development fallback. Replace VITE_WS_URL in production.
      setStatus('OPEN');
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => setStatus('OPEN');
    ws.onerror = () => setStatus('ERROR');
    ws.onclose = () => setStatus('CLOSED');
    ws.onmessage = (event) => {
      const receivedAt = performance.now();
      if (pingSentAt.current !== null) setLatencyMs(Math.max(0, Math.round(receivedAt - pingSentAt.current)));
      setLastMessageAt(Date.now());
      try {
        const payload = JSON.parse(event.data) as MarketTick;
        if (payload.type === 'PRICE_TICK') listenersRef.current.forEach((handler) => handler(payload));
      } catch {
        // Ignore malformed frames; production can route this to telemetry.
      }
    };
    return () => ws.close();
  }, []);

  const send = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  const subscribe = useCallback((handler: (tick: MarketTick) => void) => {
    listenersRef.current.add(handler);
    return () => listenersRef.current.delete(handler);
  }, []);

  // Keep the wire contract explicit; backend can respond to this ping with a PRICE_TICK or pong frame.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        pingSentAt.current = performance.now();
        wsRef.current.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
      }
    }, 5000);
    return () => window.clearInterval(id);
  }, []);

  const value = useMemo(() => ({ status, latencyMs, lastMessageAt, send, subscribe }), [status, latencyMs, lastMessageAt, send, subscribe]);
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used inside WebSocketProvider');
  return context;
}

export function placeOrder(send: (payload: unknown) => boolean, order: Omit<OrderPlacement, 'type'>) {
  return send({ type: 'ORDER_PLACEMENT', ...order });
}
