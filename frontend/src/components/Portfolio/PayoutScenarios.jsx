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

  const {
    p_double = 0,
    p_breakeven = 0,
    p_loss = 0,
    expected_profit = 0,
    upside = 0,
    downside = 0,
    distribution = [],
  } = scenarios;

  const probBars = [
    { label: 'P(2x Return)', value: p_double, color: '#006747' },
    { label: 'P(Breakeven)', value: p_breakeven, color: '#FDD835' },
    { label: 'P(Loss)', value: p_loss, color: '#ef4444' },
  ];

  return (
    <div className="space-y-4">
      {/* Probability Cards */}
      <div className="grid grid-cols-3 gap-3">
        {probBars.map((p, i) => (
          <div
            key={i}
            className="bg-gray-900/60 rounded-lg px-3 py-3 text-center"
          >
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              {p.label}
            </div>
            <div
              className="text-xl font-bold"
              style={{ color: p.color }}
            >
              {formatPct(p.value)}
            </div>
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900/60 rounded-lg px-3 py-2 text-center">
          <div className="text-[10px] uppercase text-gray-500">
            Expected Profit
          </div>
          <div
            className={`text-sm font-bold ${expected_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}
          >
            {formatCurrency(expected_profit)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2 text-center">
          <div className="text-[10px] uppercase text-gray-500">Upside</div>
          <div className="text-sm font-bold text-green-400">
            {formatCurrency(upside)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg px-3 py-2 text-center">
          <div className="text-[10px] uppercase text-gray-500">Downside</div>
          <div className="text-sm font-bold text-red-400">
            {formatCurrency(downside)}
          </div>
        </div>
      </div>

      {/* Distribution Histogram */}
      {distribution.length > 0 && (
        <div className="h-48">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">
            Outcome Distribution
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 9, fill: '#6b7280' }}
                angle={-30}
                textAnchor="end"
                height={40}
              />
              <YAxis
                tick={{ fontSize: 9, fill: '#6b7280' }}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
                formatter={(val) => [`${(val * 100).toFixed(1)}%`, 'Probability']}
              />
              <ReferenceLine x="Breakeven" stroke="#FDD835" strokeDasharray="5 5" />
              <Bar dataKey="probability" radius={[2, 2, 0, 0]}>
                {distribution.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={
                      entry.profit >= 0
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
      )}
    </div>
  );
}
