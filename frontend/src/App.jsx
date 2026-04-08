import { useState, useEffect, useCallback } from 'react';
import clsx from 'clsx';
import {
  Gavel,
  Users,
  Brain,
  Briefcase,
  History,
  ClipboardCheck,
  RefreshCw,
} from 'lucide-react';

import AuctionPanel from './components/AuctionTracker/AuctionPanel';
import GolferBoard from './components/GolferBoard/GolferBoard';
import StrategyPanel from './components/Strategy/StrategyPanel';
import PortfolioPanel from './components/Portfolio/PortfolioPanel';
import BacktestPanel from './components/BacktestPanel';
import ScorecardPanel from './components/Scorecard/ScorecardPanel';
import LiveMode from './components/LiveMode/LiveMode';
import LiveModeToggle from './components/LiveMode/LiveModeToggle';

const TABS = [
  { id: 'auction', label: 'Auction', icon: Gavel },
  { id: 'field', label: 'Field', icon: Users },
  { id: 'strategy', label: 'Strategy', icon: Brain },
  { id: 'portfolio', label: 'Portfolio', icon: Briefcase },
  { id: 'backtest', label: 'Backtest', icon: History },
  { id: 'scorecard', label: 'Scorecard', icon: ClipboardCheck },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('auction');
  const [liveMode, setLiveMode] = useState(false);

  const toggleLiveMode = useCallback(() => {
    setLiveMode((prev) => !prev);
  }, []);

  // Global 'L' key to toggle live mode (only when not typing in an input)
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'l' || e.key === 'L') {
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) {
          return;
        }
        e.preventDefault();
        toggleLiveMode();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [toggleLiveMode]);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-900/95 border-b border-gray-800 sticky top-0 z-40 backdrop-blur-sm">
        <div className="max-w-screen-2xl mx-auto px-4">
          <div className="flex items-center justify-between h-14">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-augusta rounded-lg flex items-center justify-center">
                <span className="text-white font-black text-sm">M</span>
              </div>
              <div>
                <h1 className="text-sm font-bold text-white leading-tight">
                  Masters Calcutta
                </h1>
                <p className="text-[10px] text-gray-500 leading-tight">
                  Auction Intelligence System
                </p>
              </div>
            </div>

            {/* Tab Navigation */}
            <nav className="flex items-center gap-1">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={clsx(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                      isActive
                        ? 'bg-augusta/20 text-gold border border-augusta/40'
                        : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">{tab.label}</span>
                  </button>
                );
              })}
            </nav>

            {/* Live Indicator */}
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">
                Live
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-screen-2xl mx-auto px-4 py-4">
        {activeTab === 'auction' && <AuctionPanel />}
        {activeTab === 'field' && <GolferBoard />}
        {activeTab === 'strategy' && <StrategyPanel />}
        {activeTab === 'portfolio' && <PortfolioPanel />}
        {activeTab === 'backtest' && <BacktestPanel />}
        {activeTab === 'scorecard' && <ScorecardPanel />}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-3 mt-8">
        <div className="max-w-screen-2xl mx-auto px-4 text-center text-[10px] text-gray-600">
          Masters Calcutta Auction Intelligence | Model-driven bidding
          strategy
        </div>
      </footer>

      {/* Live Mode Toggle + Overlay */}
      <LiveModeToggle onClick={toggleLiveMode} />
      <LiveMode open={liveMode} onClose={() => setLiveMode(false)} />
    </div>
  );
}
