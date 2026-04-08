import { useState, useEffect } from 'react';
import { X, Printer } from 'lucide-react';
import { getRecommendations, getAntiConsensus, getQuickSheet } from '../../api/client';
import { useAuction } from '../../hooks/useAuction';
import { formatCurrency, formatPct } from '../../utils/format';

export default function IntelBrief({ onClose }) {
  const { auction } = useAuction();
  const [recs, setRecs] = useState(null);
  const [antiConsensus, setAntiConsensus] = useState(null);
  const [cheatSheet, setCheatSheet] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
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
    })();
  }, []);

  const bankroll = auction?.my_bankroll || 0;
  const valuePlays = recs?.value_plays || [];
  const acPicks = antiConsensus?.picks || antiConsensus || [];

  // Top 5 targets: must_bid or good_value, sorted by max_bid desc
  const sheetData = cheatSheet || [];
  const topTargets = sheetData
    .filter((r) => r.alert_level === 'must_bid' || r.alert_level === 'good_value')
    .sort((a, b) => (b.max_bid || 0) - (a.max_bid || 0))
    .slice(0, 5);

  // Avoid list: where model < consensus (overvalued)
  const avoidList = sheetData
    .filter((r) => r.model_win_prob != null && r.consensus_win_prob != null && r.model_win_prob < r.consensus_win_prob)
    .sort((a, b) => (a.model_win_prob - a.consensus_win_prob) - (b.model_win_prob - b.consensus_win_prob))
    .slice(0, 5);

  // Top 5 by EV (using value plays sorted by max_bid as proxy)
  const top5EV = sheetData
    .sort((a, b) => (b.max_bid || 0) - (a.max_bid || 0))
    .slice(0, 5)
    .map((r) => r.name);

  // Anti-consensus plays (biggest model > consensus gap)
  const antiConsensusPlays = (Array.isArray(acPicks) ? acPicks : [])
    .filter((p) => p.model_win_prob != null && p.consensus_win_prob != null)
    .sort((a, b) => (b.model_win_prob - b.consensus_win_prob) - (a.model_win_prob - a.consensus_win_prob))
    .slice(0, 3);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
        <div className="bg-white rounded-xl p-8 text-gray-900 text-sm">
          Loading intel brief...
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center overflow-auto print:bg-white print:relative print:inset-auto">
      <div className="bg-white text-gray-900 rounded-xl shadow-2xl max-w-3xl w-full mx-4 my-8 print:shadow-none print:rounded-none print:mx-0 print:my-0 print:max-w-none">
        {/* Print/Close controls - hide on print */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 print:hidden">
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs font-medium text-gray-700 transition-colors"
          >
            <Printer className="w-3.5 h-3.5" />
            Print
          </button>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <div className="px-8 py-6 space-y-6 print:px-12 print:py-8">
          {/* Title */}
          <div className="text-center border-b border-gray-300 pb-4">
            <h1 className="text-xl font-black text-gray-900 uppercase tracking-wider">
              Masters 2026 Calcutta -- Intel Brief
            </h1>
            <p className="text-xs text-gray-500 mt-1">
              Generated {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </p>
          </div>

          {/* Section 1: Top 5 Targets */}
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-200 pb-1 mb-3">
              1. Your Top 5 Targets
            </h2>
            {topTargets.length === 0 ? (
              <p className="text-xs text-gray-500 italic">Configure auction to see targets</p>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-1.5 font-semibold text-gray-600 w-8">Rank</th>
                    <th className="text-left py-1.5 font-semibold text-gray-600">Name</th>
                    <th className="text-right py-1.5 font-semibold text-gray-600 w-20">Max Bid</th>
                    <th className="text-right py-1.5 font-semibold text-gray-600 w-16">Win%</th>
                    <th className="text-right py-1.5 font-semibold text-gray-600 w-20">Alert</th>
                  </tr>
                </thead>
                <tbody>
                  {topTargets.map((t, i) => (
                    <tr key={t.golfer_id || i} className="border-b border-gray-100">
                      <td className="py-1.5 font-bold text-gray-900">{i + 1}</td>
                      <td className="py-1.5 font-medium text-gray-900">{t.name}</td>
                      <td className="py-1.5 text-right font-mono font-bold text-gray-900">
                        {formatCurrency(t.max_bid)}
                      </td>
                      <td className="py-1.5 text-right font-mono text-gray-700">
                        {formatPct(t.model_win_prob)}
                      </td>
                      <td className="py-1.5 text-right">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                          t.alert_level === 'must_bid' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {t.alert_level?.replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Section 2: Avoid These */}
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-200 pb-1 mb-3">
              2. Avoid These
            </h2>
            {avoidList.length === 0 ? (
              <p className="text-xs text-gray-500 italic">No overvalued golfers detected</p>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-1.5 font-semibold text-gray-600">Name</th>
                    <th className="text-left py-1.5 font-semibold text-gray-600">Why Overpriced</th>
                  </tr>
                </thead>
                <tbody>
                  {avoidList.map((a, i) => {
                    const gap = ((a.consensus_win_prob - a.model_win_prob) * 100).toFixed(1);
                    return (
                      <tr key={a.golfer_id || i} className="border-b border-gray-100">
                        <td className="py-1.5 font-medium text-gray-900">{a.name}</td>
                        <td className="py-1.5 text-gray-600">
                          Consensus inflated by {gap}% vs model. Market will overpay.
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Section 3: Budget Plan */}
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-200 pb-1 mb-3">
              3. Budget Plan
            </h2>
            <div className="text-xs text-gray-700 space-y-1">
              <p>
                <span className="font-bold">Total bankroll:</span>{' '}
                <span className="font-mono">{formatCurrency(bankroll)}</span>
              </p>
              <p>
                Spend <span className="font-bold">40%</span> ({formatCurrency(bankroll * 0.4)}) on your top 2.
                Spend <span className="font-bold">35%</span> ({formatCurrency(bankroll * 0.35)}) on the next 3.
                Keep <span className="font-bold">25%</span> ({formatCurrency(bankroll * 0.25)}) for mid-auction value.
              </p>
            </div>
          </div>

          {/* Section 4: If You Can Only Buy 5 */}
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-200 pb-1 mb-3">
              4. If You Can Only Buy 5
            </h2>
            <p className="text-xs text-gray-900 font-medium">
              {top5EV.length > 0 ? top5EV.join(', ') : 'Configure auction to see top EV picks'}
            </p>
          </div>

          {/* Section 5: Key Anti-Consensus Plays */}
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-200 pb-1 mb-3">
              5. Key Anti-Consensus Plays
            </h2>
            {antiConsensusPlays.length === 0 ? (
              <p className="text-xs text-gray-500 italic">No anti-consensus plays found</p>
            ) : (
              <div className="space-y-2">
                {antiConsensusPlays.map((p, i) => {
                  const edge = ((p.model_win_prob - p.consensus_win_prob) * 100).toFixed(1);
                  return (
                    <p key={i} className="text-xs text-gray-700">
                      <span className="font-bold text-gray-900">{p.name}</span> --
                      Model sees {edge}% more win probability than consensus.
                      {p.model_win_prob > 0.05 ? ' Serious contender the market is sleeping on.' : ' Under-the-radar value.'}
                    </p>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-300 pt-3 text-center">
            <p className="text-[10px] text-gray-400">
              Generated by Masters Calcutta Engine -- model probabilities from ELO + Monte Carlo + Regression ensemble
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
