import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import { formatCurrency, formatPct } from '../../utils/format';

export default function PayoutScenarios({ scenarios }) {
  if (!scenarios) {
    return (
      <div className="text-center py-6 text-gray-600 text-sm">
        No scenario data available
      </div>
    );
  }

  // API returns: total_pool, payout_structure, golfer_projections,
  // total_invested, total_expected_payout, expected_profit, expected_roi_pct, win_probability_any
  const {
    total_pool = 0,
    total_invested = 0,
    total_expected_payout = 0,
    expected_profit = 0,
    expected_roi_pct = 0,
    win_probability_any = 0,
    golfer_projections = [],
  } = scenarios;

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Total Pool
          </div>
          <div className="text-lg font-bold text-gold">
            {formatCurrency(total_pool)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Expected Payout
          </div>
          <div className="text-lg font-bold text-green-400">
            {formatCurrency(total_expected_payout)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Expected Profit
          </div>
          <div
            className={`text-lg font-bold ${expected_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}
          >
            {formatCurrency(expected_profit)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            P(Any Win)
          </div>
          <div className="text-lg font-bold text-gold">
            {formatPct(win_probability_any)}
          </div>
        </div>
      </div>

      {/* ROI Summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-2 text-center">
          <div className="text-[10px] uppercase text-gray-500">
            Total Invested
          </div>
          <div className="text-sm font-bold text-gray-300">
            {formatCurrency(total_invested)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2 text-center">
          <div className="text-[10px] uppercase text-gray-500">
            Expected ROI
          </div>
          <div
            className={`text-sm font-bold ${expected_roi_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}
          >
            {formatPct(expected_roi_pct / 100)}
          </div>
        </div>
      </div>

      {/* Golfer Projections */}
      {golfer_projections.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">
            Golfer Projections
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={golfer_projections.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 9, fill: '#6b7280' }}
                  angle={-30}
                  textAnchor="end"
                  height={40}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: '#6b7280' }}
                  tickFormatter={(v) => `$${v}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                  formatter={(val) => [formatCurrency(val), 'Expected Payout']}
                />
                <Bar dataKey="expected_payout" radius={[2, 2, 0, 0]}>
                  {golfer_projections.slice(0, 10).map((entry, i) => (
                    <Cell
                      key={i}
                      fill={
                        (entry.expected_payout || 0) >= (entry.purchase_price || 0)
                          ? '#006747'
                          : '#ef4444'
                      }
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
