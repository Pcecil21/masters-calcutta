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

  // Generate EV curve data (price vs EV)
  const evCurve = [];
  const modelValue = detail.model_value || 100;
  for (let price = 10; price <= modelValue * 3; price += 10) {
    const ev = detail.expected_payout
      ? detail.expected_payout / price
      : (modelValue / price) * 1;
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
            <span>Odds: {detail.odds || '--'}</span>
            <span>Model Value: {formatCurrency(detail.model_value)}</span>
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
            {formatPct(detail.model_win_pct)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Top 5%</div>
          <div className="text-sm font-bold text-green-300">
            {formatPct(detail.model_top5_pct)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2">
          <div className="text-[10px] uppercase text-gray-500">Top 10%</div>
          <div className="text-sm font-bold text-yellow-300">
            {formatPct(detail.model_top10_pct)}
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

      {/* Model Breakdown */}
      {detail.model_breakdown && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-1">
            <Target className="w-3 h-3" />
            Model Breakdown
          </h4>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(detail.model_breakdown).map(([key, val]) => (
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

      {/* Augusta Factors & Edge Narrative */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {detail.augusta_factors && (
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-1">
              <Award className="w-3 h-3" />
              Augusta Factors
            </h4>
            <ul className="space-y-1">
              {Object.entries(detail.augusta_factors).map(([key, val]) => (
                <li
                  key={key}
                  className="flex items-center justify-between text-xs bg-gray-900/40 rounded px-3 py-1.5"
                >
                  <span className="text-gray-400 capitalize">
                    {key.replace(/_/g, ' ')}
                  </span>
                  <span className="text-white font-mono">
                    {typeof val === 'number' ? val.toFixed(1) : String(val)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {detail.edge_narrative && (
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">
              Edge Narrative
            </h4>
            <p className="text-xs text-gray-300 leading-relaxed bg-gray-900/40 rounded p-3">
              {detail.edge_narrative}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
