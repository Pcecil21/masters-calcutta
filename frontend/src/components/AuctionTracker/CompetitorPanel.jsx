import { useState, useEffect } from 'react';
import { Users, RefreshCw } from 'lucide-react';
import { getCompetitors } from '../../api/client';
import { formatCurrency } from '../../utils/format';

const PROFILE_BADGES = {
  favorite_hunter: { label: 'Favorite Hunter', color: 'bg-orange-500/20 text-orange-400 border-orange-500/40' },
  value_seeker: { label: 'Value Seeker', color: 'bg-green-500/20 text-green-400 border-green-500/40' },
  spray_and_pray: { label: 'Spray and Pray', color: 'bg-gray-500/20 text-gray-400 border-gray-500/40' },
  balanced: { label: 'Balanced', color: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
  sniper: { label: 'Sniper', color: 'bg-purple-500/20 text-purple-400 border-purple-500/40' },
};

function getBadge(profile) {
  if (!profile) return PROFILE_BADGES.balanced;
  const key = profile.toLowerCase().replace(/\s+/g, '_');
  return PROFILE_BADGES[key] || { label: profile, color: 'bg-gray-500/20 text-gray-400 border-gray-500/40' };
}

export default function CompetitorPanel() {
  const [competitors, setCompetitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCompetitors = async () => {
    try {
      const data = await getCompetitors();
      setCompetitors(data?.competitors || data || []);
    } catch (err) {
      setError('Could not load competitor data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, []);

  // Re-fetch can be triggered externally via key or polling
  const nonMe = competitors.filter(
    (c) => c.buyer && c.buyer.toLowerCase() !== 'me'
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <RefreshCw className="w-4 h-4 text-augusta animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-augusta" />
        Competitor Intel
      </h3>

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400 mb-3">
          {error}
        </div>
      )}

      {nonMe.length === 0 ? (
        <div className="text-center py-4 text-gray-600 text-xs">
          No competitor bids recorded yet
        </div>
      ) : (
        <div className="space-y-3">
          {nonMe.map((comp, i) => {
            const badge = getBadge(comp.profile);
            const holdings = (comp.holdings || []).sort(
              (a, b) => (b.price || 0) - (a.price || 0)
            );
            return (
              <div
                key={i}
                className="bg-gray-900/40 border border-gray-700/30 rounded-lg p-3"
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">
                      {comp.buyer}
                    </span>
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${badge.color}`}
                    >
                      {badge.label}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400 font-mono">
                    {formatCurrency(comp.total_spent)} spent
                  </span>
                </div>

                {/* Implication */}
                {comp.implication && (
                  <p className="text-[11px] text-gray-500 italic mb-2">
                    {comp.implication}
                  </p>
                )}

                {/* Holdings */}
                {holdings.length > 0 && (
                  <div className="space-y-0.5">
                    {holdings.map((h, j) => (
                      <div
                        key={j}
                        className="flex items-center justify-between px-2 py-1 text-[11px]"
                      >
                        <span className="text-gray-300 truncate">{h.golfer}</span>
                        <span className="text-gray-500 font-mono ml-2">
                          {formatCurrency(h.price)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
