import { useState, useMemo, useCallback } from 'react';
import {
  Settings,
  RefreshCw,
  DollarSign,
  Users,
  TrendingUp,
  Gauge,
} from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { usePolling } from '../../hooks/usePolling';
import { formatCurrency, formatPct, evColor } from '../../utils/format';
import StatCard from '../common/StatCard';
import AlertBadge from '../common/AlertBadge';
import BidForm from './BidForm';
import QuickPrice from './QuickPrice';
import AlertTicker from './AlertTicker';
import BidHistory from './BidHistory';
import AuctionConfig from './AuctionConfig';

export default function AuctionPanel() {
  const { auction, golfers, alerts, refresh, loading } = useAuction();
  const [configOpen, setConfigOpen] = useState(false);
  const [preselectedGolfer, setPreselectedGolfer] = useState(null);

  // Auto-refresh every 10 seconds during live auction
  usePolling(refresh, 10000, true);

  const poolSize = auction?.total_pool || 0;
  const bankroll = auction?.my_bankroll || 0;
  const remaining = auction?.remaining_bankroll || 0;
  const spent = bankroll - remaining;

  const soldIds = useMemo(
    () => new Set(auction?.golfers_sold || []),
    [auction?.golfers_sold]
  );
  const unsold = useMemo(
    () => golfers.filter((g) => !soldIds.has(g.id)),
    [golfers, soldIds]
  );
  const golfersRemaining = unsold.length;
  const totalGolfers = golfers.length || 1;

  // Spend rate: what % of bankroll is spent vs % of golfers sold
  const pctGolfersSold = (totalGolfers - golfersRemaining) / totalGolfers;
  const pctBankrollSpent = bankroll ? spent / bankroll : 0;
  const spendRate =
    pctGolfersSold > 0
      ? (pctBankrollSpent / pctGolfersSold).toFixed(2)
      : '--';
  const spendRateNum = parseFloat(spendRate);

  const handleQuickBid = useCallback((golfer) => {
    setPreselectedGolfer(golfer);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-6 h-6 text-augusta animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard
          label="Total Pool"
          value={formatCurrency(poolSize)}
          className="border-l-2 border-l-gold"
        />
        <StatCard
          label="My Bankroll"
          value={formatCurrency(remaining)}
          subtitle={`${formatCurrency(spent)} spent`}
          trend={remaining > bankroll * 0.3 ? 'up' : 'down'}
          className="border-l-2 border-l-augusta"
        />
        <StatCard
          label="Spent"
          value={formatCurrency(spent)}
          subtitle={`${formatPct(pctBankrollSpent)} of bankroll`}
        />
        <StatCard
          label="Golfers Left"
          value={golfersRemaining}
          subtitle={`of ${totalGolfers}`}
        />
        <StatCard
          label="Spend Rate"
          value={`${spendRate}x`}
          subtitle={!isNaN(spendRateNum) ? (spendRateNum > 1.2 ? 'Spending fast' : spendRateNum < 0.8 ? 'Under-spending' : 'On pace') : 'No data'}
          trend={
            !isNaN(spendRateNum) ? (spendRateNum > 1.2 ? 'down' : spendRateNum < 0.8 ? 'up' : 'neutral') : 'neutral'
          }
        />
      </div>

      {/* Alert Ticker */}
      <AlertTicker />

      {/* Quick Price Check */}
      <QuickPrice />

      {/* Main Content: Bid Form + History | Remaining Golfers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Bid Form + History */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-gold" />
                Record Bid
              </h2>
              <button
                onClick={() => setConfigOpen(true)}
                className="p-1.5 hover:bg-gray-700/50 rounded-lg transition-colors"
                title="Auction settings"
              >
                <Settings className="w-4 h-4 text-gray-500" />
              </button>
            </div>
            <BidForm
              preselectedGolfer={preselectedGolfer}
              onClearPreselect={() => setPreselectedGolfer(null)}
            />
          </div>

          <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
            <BidHistory />
          </div>
        </div>

        {/* Right: Remaining Golfers Mini-Board */}
        <div className="lg:col-span-2 bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Users className="w-4 h-4 text-augusta" />
              Remaining Field
              <span className="text-xs text-gray-500 font-normal">
                ({golfersRemaining})
              </span>
            </h2>
            <button
              onClick={refresh}
              className="p-1.5 hover:bg-gray-700/50 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5 text-gray-500" />
            </button>
          </div>

          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] uppercase tracking-wider text-gray-600 border-b border-gray-700/50 mb-1">
            <span className="w-8 text-right">#</span>
            <span className="flex-1">Golfer</span>
            <span className="w-14 text-right">Win%</span>
            <span className="w-12 text-right">EV</span>
            <span className="w-6" />
          </div>

          {/* Rows */}
          <div className="max-h-[500px] overflow-y-auto space-y-0.5">
            {unsold
              .sort((a, b) => (b.ev_score || 0) - (a.ev_score || 0))
              .map((g) => (
                <div
                  key={g.id}
                  onClick={() => handleQuickBid(g)}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-augusta/10 rounded cursor-pointer transition-colors group text-xs"
                >
                  <span className="w-8 text-right text-gray-500 font-mono">
                    {g.world_ranking || '--'}
                  </span>
                  <span className="flex-1 font-medium text-gray-200 group-hover:text-white truncate">
                    {g.name}
                  </span>
                  <span className="w-14 text-right text-gray-400 font-mono">
                    {formatPct(g.model_win_prob)}
                  </span>
                  <span
                    className={`w-12 text-right font-mono font-bold ${evColor(g.ev_score)}`}
                  >
                    {g.ev_score != null ? g.ev_score.toFixed(1) : '--'}
                  </span>
                  <span className="w-6 text-center opacity-0 group-hover:opacity-100 text-gold transition-opacity">
                    +
                  </span>
                </div>
              ))}
            {unsold.length === 0 && (
              <div className="text-center py-8 text-gray-600 text-sm">
                All golfers have been auctioned
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Config Modal */}
      <AuctionConfig open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
