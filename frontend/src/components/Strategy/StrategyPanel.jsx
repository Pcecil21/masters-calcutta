import { useState, useEffect } from 'react';
import {
  Target,
  TrendingUp,
  DollarSign,
  RefreshCw,
  Lightbulb,
  BarChart3,
} from 'lucide-react';
import { getRecommendations, getAntiConsensus } from '../../api/client';
import { formatCurrency, formatPct, formatMultiplier } from '../../utils/format';
import AlertBadge from '../common/AlertBadge';
import AntiConsensusChart from './AntiConsensusChart';

export default function StrategyPanel() {
  const [recs, setRecs] = useState(null);
  const [antiConsensus, setAntiConsensus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [r, ac] = await Promise.all([
        getRecommendations().catch(() => null),
        getAntiConsensus().catch(() => null),
      ]);
      setRecs(r);
      setAntiConsensus(ac);
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
                    {formatMultiplier(play.ev_multiple)}
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
                  {formatPct(pick.model_prob)}
                </span>
                <span className="text-gray-500">Consensus:</span>
                <span className="text-gray-400 font-mono w-14 text-right">
                  {formatPct(pick.consensus_prob)}
                </span>
                <span className="text-gold font-bold font-mono w-12 text-right">
                  {pick.divergence
                    ? `+${(pick.divergence * 100).toFixed(1)}%`
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
    </div>
  );
}
