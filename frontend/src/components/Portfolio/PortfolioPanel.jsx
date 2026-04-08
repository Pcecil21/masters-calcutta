import { useState, useEffect } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  Briefcase,
  RefreshCw,
  TrendingUp,
  Shield,
  Target,
} from 'lucide-react';
import {
  getPortfolio,
  getPortfolioOptimization,
  getExpectedPayout,
} from '../../api/client';
import { useAuction } from '../../hooks/useAuction';
import {
  formatCurrency,
  formatPct,
  formatMultiplier,
  evColor,
} from '../../utils/format';
import StatCard from '../common/StatCard';
import PayoutScenarios from './PayoutScenarios';

const PIE_COLORS = [
  '#006747',
  '#FDD835',
  '#00875f',
  '#F9A825',
  '#004d35',
  '#e5c100',
  '#38a169',
  '#d69e2e',
];

export default function PortfolioPanel() {
  const { portfolio: ctxPortfolio, golfers } = useAuction();
  const [portfolio, setPortfolio] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [payout, setPayout] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [p, o, pay] = await Promise.all([
        getPortfolio().catch(() => null),
        getPortfolioOptimization().catch(() => null),
        getExpectedPayout().catch(() => null),
      ]);
      setPortfolio(p);
      setOptimization(o);
      setPayout(pay);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [ctxPortfolio]);

  // Helper to find golfer name from ID
  const getGolferName = (golferId) => {
    const golfer = golfers.find((g) => g.id === golferId);
    return golfer?.name || `Golfer #${golferId}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-augusta animate-spin" />
      </div>
    );
  }

  // Portfolio API returns: entries[], total_invested, total_expected_value, expected_roi, risk_score
  const entries = portfolio?.entries || [];
  const totalInvested = portfolio?.total_invested || 0;
  const totalEV = portfolio?.total_expected_value || 0;
  const expectedROI = portfolio?.expected_roi || 0;
  const riskScore = portfolio?.risk_score;
  const needRecs = optimization?.recommendations || [];

  const pieData = entries.map((h) => ({
    name: getGolferName(h.golfer_id),
    value: h.purchase_price || 0,
  }));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Total Invested"
          value={formatCurrency(totalInvested)}
          className="border-l-2 border-l-gold"
        />
        <StatCard
          label="Expected Value"
          value={formatCurrency(totalEV)}
          trend={totalEV > totalInvested ? 'up' : 'down'}
          className="border-l-2 border-l-augusta"
        />
        <StatCard
          label="Expected ROI"
          value={formatPct(expectedROI)}
          trend={expectedROI > 0 ? 'up' : expectedROI < 0 ? 'down' : 'neutral'}
        />
        <StatCard
          label="Risk Score"
          value={riskScore != null ? riskScore.toFixed(1) : '--'}
          subtitle={
            riskScore != null
              ? riskScore < 3
                ? 'Conservative'
                : riskScore < 6
                  ? 'Moderate'
                  : 'Aggressive'
              : ''
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Holdings Table */}
        <div className="lg:col-span-2 bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
            <Briefcase className="w-4 h-4 text-gold" />
            My Holdings
          </h2>

          {entries.length === 0 ? (
            <div className="text-center py-8 text-gray-600 text-sm">
              No golfers in portfolio yet. Win some bids!
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] uppercase tracking-wider text-gray-600 border-b border-gray-700/50 mb-1">
                <span className="flex-1">Golfer</span>
                <span className="w-20 text-right">Price</span>
                <span className="w-16 text-right">Win%</span>
                <span className="w-16 text-right">EV</span>
                <span className="w-16 text-right">EV Mult</span>
              </div>
              <div className="space-y-0.5 max-h-72 overflow-y-auto">
                {entries.map((h, i) => {
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800/60 text-xs transition-colors"
                    >
                      <span className="flex-1 text-white font-medium truncate">
                        {getGolferName(h.golfer_id)}
                      </span>
                      <span className="w-20 text-right text-gray-300 font-mono">
                        {formatCurrency(h.purchase_price)}
                      </span>
                      <span className="w-16 text-right text-green-400 font-mono">
                        {formatPct(h.model_win_prob)}
                      </span>
                      <span
                        className={`w-16 text-right font-mono font-bold ${evColor(h.expected_value)}`}
                      >
                        {h.expected_value?.toFixed(2) || '--'}
                      </span>
                      <span
                        className={`w-16 text-right font-mono font-bold ${
                          (h.ev_multiple || 0) >= 1 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {formatMultiplier(h.ev_multiple)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Pie Chart */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
          <h2 className="text-sm font-bold text-white mb-4">Allocation</h2>
          {pieData.length === 0 ? (
            <div className="text-center py-8 text-gray-600 text-sm">
              No holdings
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    innerRadius={40}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${name} ${(percent * 100).toFixed(0)}%`
                    }
                    labelLine={{ stroke: '#4b5563' }}
                  >
                    {pieData.map((_, i) => (
                      <Cell
                        key={i}
                        fill={PIE_COLORS[i % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                    formatter={(val) => [formatCurrency(val), 'Price Paid']}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Payout Scenarios */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-gold" />
          Payout Scenarios
        </h2>
        <PayoutScenarios scenarios={payout} />
      </div>

      {/* What I Still Need */}
      {needRecs.length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-gold" />
            What You Still Need
          </h2>
          <div className="space-y-2">
            {needRecs.map((rec, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-2 bg-gray-900/40 rounded text-xs"
              >
                <span className="text-gold font-bold w-5">{i + 1}</span>
                <span className="flex-1 text-gray-300">{rec.text || rec}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
