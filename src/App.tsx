
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { TerminalLayout } from './components/TerminalLayout';
import { WebSocketProvider } from './context/WebSocketContext';
import { WatchlistsView } from './views/WatchlistsView';
import { OrderTicketView } from './views/OrderTicketView';
import { DashboardView } from './views/DashboardView';
import {
  WatchlistsMockView, OrderBooksView, PortfolioView, PositionsView, AlertsView,
  HistoryView, StrategyView, NewsView, AnalyticsView, ToolsView, SettingsView,
  OptionsView, SpotTradingView, AlgoOrdersView, PerpetualsView, FuturesView, DerivativesView
} from './views/MockWorkspaces';

export default function App(){
 return <BrowserRouter><WebSocketProvider><TerminalLayout><Routes>
  <Route path="/" element={<DashboardView/>}/>
  <Route path="/watchlists" element={<WatchlistsMockView/>}/>
  <Route path="/order-books" element={<OrderBooksView/>}/>
  <Route path="/portfolio" element={<PortfolioView/>}/>
  <Route path="/positions" element={<PositionsView/>}/>
  <Route path="/alerts" element={<AlertsView/>}/>
  <Route path="/history" element={<HistoryView/>}/>
  <Route path="/strategy" element={<StrategyView/>}/>
  <Route path="/news" element={<NewsView/>}/>
  <Route path="/analytics" element={<AnalyticsView/>}/>
  <Route path="/tools" element={<ToolsView/>}/>
  <Route path="/settings" element={<SettingsView/>}/>
  <Route path="/trade/spot-trading" element={<SpotTradingView/>}/>
  <Route path="/trade/derivatives" element={<DerivativesView/>}/>
  <Route path="/trade/algorithmic-orders" element={<AlgoOrdersView/>}/>
  <Route path="/trade/options" element={<OptionsView/>}/>
  <Route path="/trade/futures" element={<FuturesView/>}/>
  <Route path="/trade/perpetuals" element={<PerpetualsView/>}/>
  <Route path="/trade/order-ticket" element={<OrderTicketView/>}/>
 </Routes></TerminalLayout></WebSocketProvider></BrowserRouter>
}
