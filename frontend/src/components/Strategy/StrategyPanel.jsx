import { useState, useEffect } from 'react';
import {
  Target,
  TrendingUp,
  DollarSign,
  RefreshCw,
  Lightbulb,
  BarChart3,
  ClipboardList,
  FileText,
} from 'lucide-react';
import { getRecommendations, getAntiConsensus, getQuickSheet, refreshOdds } from '../../api/client';
import { formatCurrency, formatPct, formatMultiplier } from '../../utils/format';
import AlertBadge from '../common/AlertBadge';
import AntiConsensusChart from './AntiConsensusChart';
import IntelBrief from './IntelBrief';

export default function StrategyPanel() {
  const [recs, setRecs] = useState(null);
  const [antiConsensus, setAntiConsensus] = useState(null);
  const [cheatSheet, setCheatSheet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [oddsRefreshing, setOddsRefreshing] = useState(false);
  const [oddsMessage, setOddsMessage] = useState(null);
  const [showIntelBrief, setShowIntelBrief] = useState(false);

  const handleRefreshOdds = async () => {
    let apiKey = localStorage.getItem('odds_api_key');
    if (!apiKey) {
      apiKey = window.prompt('Enter your The Odds API key (free at the-odds-api.com):');
      if (!apiKey) return;
      localStorage.setItem('odds_api_key', apiKey);
    }
    setOddsRefreshing(true);
    setOddsMessage(null);
    try {
      const result = await refreshOdds(apiKey);
      const msg = `Updated ${result.updated} golfer${result.updated !== 1 ? 's' : ''}`;
      const extra = result.unmatched?.length
        ? ` | ${result.unmatched.length} unmatched`
        : '';
      setOddsMessage({ type: 'success', text: msg + extra });
      // Refresh strategy data to reflect new consensus probs
      await fetchData();
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Failed to refresh odds';
      setOddsMessage({ type: 'error', text: detail });
      // If 401, clear stored key so user is prompted again
      if (err?.response?.status === 401) {
        localStorage.removeItem('odds_api_key');
      }
    } finally {
      setOddsRefreshing(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [r, ac, qs] = await Promise.all([
        getRecommendations().catch(() => null),
        getAntiConsensus().catch(() => null),
        getQuickSheet().catch(() => null),
      ]);
      setRecs(r);
      setAntiConsensus(ac);
      setCheatSheet(qs);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-augusta animate-spin" />
      </div>
    );
  }

  const valuePlays = recs?.value_plays || [];
  const budgetAlloc = recs?.budget_allocation || {};
  const bidLimits = recs?.bid_limits || [];
  const acPicks = antiConsensus?.picks || antiConsensus || [];

  return (
    <div className="space-y-6">
      {/* Refresh Odds Bar */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleRefreshOdds}
          disabled={oddsRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 bg-augusta/20 hover:bg-augusta/30 border border-augusta/40 rounded-lg text-xs text-augusta font-medium transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${oddsRefreshing ? 'animate-spin' : ''}`} />
          {oddsRefreshing ? 'Refreshing...' : 'Refresh Live Odds'}
        </button>
        <button
          onClick={() => setShowIntelBrief(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-gold/20 hover:bg-gold/30 border border-gold/40 rounded-lg text-xs text-gold font-medium transition-colors"
        >
          <FileText className="w-3.5 h-3.5" />
          View Intel Brief
        </button>
        {oddsMessage && (
          <span
            className={`text-xs ${oddsMessage.type === 'success' ? 'text-green-400' : 'text-red-400'}`}
          >
            {oddsMessage.text}
          </span>
        )}
      </div>

      {/* Top Value Plays */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Target className="w-4 h-4 text-gold" />
            Top Value Plays
          </h2>
          <button
            onClick={fetchData}
            className="p-1.5 hover:bg-gray-700/50 rounded-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-gray-500" />
          </button>
        </div>

        {valuePlays.length === 0 ? (
          <div className="text-center py-6 text-gray-600 text-sm">
            No recommendations available. Configure the auction first.
          </div>
        ) : (
          <div className="space-y-2">
            {valuePlays.slice(0, 10).map((play, i) => (
              <div
                key={i}
                className="flex items-start gap-3 px-4 py-3 bg-gray-900/40 rounded-lg border border-gray-700/30 hover:border-augusta/30 transition-colors"
              >
                <span className="text-gold font-bold font-mono text-sm w-6 text-right shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm">
                      {play.name}
                    </span>
                    {play.alert_level && (
                      <AlertBadge level={play.alert_level} />
                    )}
                  </div>
                  {play.reasoning && (
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                      {play.reasoning}
                    </p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-green-400">
                    {play.confidence != null
                      ? `${(play.confidence * 100).toFixed(0)}%`
                      : formatMultiplier(play.ev_multiple)}
                  </div>
                  <div className="text-[10px] text-gray-500">
                    max {formatCurrency(play.max_bid)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Anti-Consensus Picks */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <Lightbulb className="w-4 h-4 text-gold" />
          Anti-Consensus Divergence
        </h2>
        <AntiConsensusChart data={Array.isArray(acPicks) ? acPicks : []} />

        {Array.isArray(acPicks) && acPicks.length > 0 && (
          <div className="mt-4 space-y-1.5">
            {acPicks.slice(0, 5).map((pick, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-2 bg-gray-900/40 rounded text-xs"
              >
                <span className="text-white font-medium flex-1">
                  {pick.name}
                </span>
                <span className="text-gray-500">Model:</span>
                <span className="text-green-400 font-mono w-14 text-right">
                  {formatPct(pick.model_win_prob)}
                </span>
                <span className="text-gray-500">Consensus:</span>
                <span className="text-gray-400 font-mono w-14 text-right">
                  {formatPct(pick.consensus_win_prob)}
                </span>
                <span className="text-gold font-bold font-mono w-12 text-right">
                  {pick.model_win_prob != null && pick.consensus_win_prob != null
                    ? `+${((pick.model_win_prob - pick.consensus_win_prob) * 100).toFixed(1)}%`
                    : '--'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Budget Allocation & Bid Limits */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Budget Allocation */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
            <DollarSign className="w-4 h-4 text-gold" />
            Budget Allocation
          </h2>
          {Object.keys(budgetAlloc).length === 0 ? (
            <div className="text-center py-4 text-gray-600 text-xs">
              Configure auction to see budget recommendations
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(budgetAlloc).map(([tier, amount]) => (
                <div key={tier} className="flex items-center justify-between">
                  <span className="text-xs text-gray-400 capitalize">
                    {tier.replace(/_/g, ' ')}
                  </span>
                  <span className="text-sm font-bold text-white">
                    {formatCurrency(amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recommended Bid Limits */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-gold" />
            Bid Limits
          </h2>
          {bidLimits.length === 0 ? (
            <div className="text-center py-4 text-gray-600 text-xs">
              No bid limits calculated yet
            </div>
          ) : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {bidLimits.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-3 py-1.5 bg-gray-900/40 rounded text-xs"
                >
                  <span className="text-gray-300">{item.name}</span>
                  <span className="text-gold font-mono font-bold">
                    {formatCurrency(item.max_bid)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Auction Cheat Sheet */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-gold" />
            Auction Cheat Sheet
          </h2>
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            Print this for auction day
          </span>
        </div>

        {!cheatSheet || cheatSheet.length === 0 ? (
          <div className="text-center py-6 text-gray-600 text-sm">
            Configure the auction to generate your cheat sheet.
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center gap-2 px-3 py-2 text-[10px] uppercase tracking-wider text-gray-500 border-b border-gray-700/50 mb-1">
              <span className="flex-1">Name</span>
              <span className="w-20 text-right">Max Bid</span>
              <span className="w-24 text-right">Breakeven</span>
              <span className="w-24 text-right">Alert</span>
            </div>
            {/* Rows */}
            <div className="max-h-[400px] overflow-y-auto space-y-0.5 print:max-h-none">
              {cheatSheet.map((row) => {
                const alertStyles = {
                  must_bid: 'text-red-400 bg-red-500/20',
                  good_value: 'text-green-400 bg-green-500/20',
                  fair: 'text-gray-400 bg-gray-500/20',
                  overpriced: 'text-orange-400 bg-orange-500/20',
                  avoid: 'text-red-500 bg-red-500/10',
                };
                const style = alertStyles[row.alert_level] || alertStyles.fair;
                return (
                  <div
                    key={row.golfer_id}
                    className="flex items-center gap-2 px-3 py-1.5 bg-gray-900/40 rounded text-xs hover:bg-gray-900/60 transition-colors"
                  >
                    <span className="flex-1 text-gray-200 font-medium truncate">
                      {row.name}
                    </span>
                    <span className="w-20 text-right font-mono font-bold text-gold">
                      {formatCurrency(row.max_bid)}
                    </span>
                    <span className="w-24 text-right font-mono text-gray-400">
                      {formatCurrency(row.breakeven_price)}
                    </span>
                    <span className="w-24 text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${style}`}
                      >
                        {row.alert_level.replace('_', ' ')}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Intel Brief Modal */}
      {showIntelBrief && (
        <IntelBrief onClose={() => setShowIntelBrief(false)} />
      )}
    </div>
  );
}
