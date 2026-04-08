import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { X, TrendingUp, Target, Award } from 'lucide-react';
import { getGolfer } from '../../api/client';
import { formatCurrency, formatPct, formatPctRaw } from '../../utils/format';

export default function GolferDetail({ golferId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!golferId) return;
    setLoading(true);
    getGolfer(golferId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [golferId]);

  if (!golferId) return null;

  if (loading) {
    return (
      <div className="bg-gray-800/80 border border-gray-700 rounded-xl p-6 text-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="bg-gray-800/80 border border-gray-700 rounded-xl p-6 text-center text-gray-500">
        Could not load golfer details
      </div>
    );
  }

  // Use ev_score as model dollar value estimate
  const modelValue = detail.ev_score || 100;

  // Generate EV curve data (price vs EV multiple)
  const evCurve = [];
  for (let price = 10; price <= modelValue * 3; price += 10) {
    const ev = modelValue / price;
    evCurve.push({ price, ev: parseFloat(ev.toFixed(2)) });
  }

  return (
    <div className="bg-gray-800/80 border border-gray-700 rounded-xl p-5 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-white">{detail.name}</h3>
          <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
            <span>World Rank: #{detail.world_ranking || '--'}</span>
            <span>Odds: {detail.odds_to_win || '--'}</span>
            <span>EV Score: {detail.ev_score != null ? detail.ev_score.toFixed(2) : '--'}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Win%</div>
          <div className="text-sm font-bold text-green-400">
            {formatPct(detail.model_win_prob)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Top 5%</div>
          <div className="text-sm font-bold text-green-300">
            {formatPct(detail.model_top5_prob)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Top 10%</div>
          <div className="text-sm font-bold text-yellow-300">
            {formatPct(detail.model_top10_prob)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">
            Anti-Consensus
          </div>
          <div className="text-sm font-bold text-gold">
            {detail.anti_consensus_score?.toFixed(2) || '--'}
          </div>
        </div>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Top 20%</div>
          <div className="text-sm font-bold text-orange-300">
            {formatPct(detail.model_top20_prob)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Make Cut%</div>
          <div className="text-sm font-bold text-gray-300">
            {formatPct(detail.model_cut_prob)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Masters Apps</div>
          <div className="text-sm font-bold text-gray-300">
            {detail.masters_appearances ?? '--'}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Masters Wins</div>
          <div className="text-sm font-bold text-gold">
            {detail.masters_wins ?? '--'}
          </div>
        </div>
      </div>

      {/* Augusta History & Recent Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Recent Form Score</div>
          <div className="text-sm font-bold text-gray-200">
            {detail.recent_form_score != null ? detail.recent_form_score.toFixed(2) : '--'}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Augusta History Score</div>
          <div className="text-sm font-bold text-gray-200">
            {detail.augusta_history_score != null ? detail.augusta_history_score.toFixed(2) : '--'}
          </div>
        </div>
      </div>

      {/* EV Curve Chart */}
      <div>
        <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-1">
          <TrendingUp className="w-3 h-3" />
          EV vs Purchase Price
        </h4>
        <div className="h-48 bg-gray-900/40 rounded-lg p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={evCurve}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="price"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                tickFormatter={(v) => `$${v}`}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#6b7280' }}
                tickFormatter={(v) => `${v}x`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(val) => [`${val}x`, 'EV']}
                labelFormatter={(label) => `Price: $${label}`}
              />
              <ReferenceLine
                y={1}
                stroke="#FDD835"
                strokeDasharray="5 5"
                label={{ value: 'Breakeven', fill: '#FDD835', fontSize: 10 }}
              />
              {modelValue && (
                <ReferenceLine
                  x={modelValue}
                  stroke="#006747"
                  strokeDasharray="5 5"
                  label={{
                    value: 'Model Value',
                    fill: '#006747',
                    fontSize: 10,
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="ev"
                stroke="#006747"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Current Season Stats */}
      {detail.current_season_stats && Object.keys(detail.current_season_stats).length > 0 && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-1">
            <Target className="w-3 h-3" />
            Current Season Stats
          </h4>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(detail.current_season_stats).map(([key, val]) => (
              <div
                key={key}
                className="bg-gray-900/60 rounded px-3 py-2 text-center"
              >
                <div className="text-[10px] text-gray-500 capitalize">
                  {key.replace(/_/g, ' ')}
                </div>
                <div className="text-sm font-bold text-gray-200">
                  {typeof val === 'number' ? val.toFixed(2) : val}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Consensus vs Model */}
      {detail.consensus_win_prob != null && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-1">
            <Award className="w-3 h-3" />
            Model vs Consensus
          </h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-900/60 rounded px-3 py-2">
              <div className="text-[10px] text-gray-500">Model Win%</div>
              <div className="text-sm font-bold text-green-400">
                {formatPct(detail.model_win_prob)}
              </div>
            </div>
            <div className="bg-gray-900/60 rounded px-3 py-2">
              <div className="text-[10px] text-gray-500">Consensus Win%</div>
              <div className="text-sm font-bold text-gray-400">
                {formatPct(detail.consensus_win_prob)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
