import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { History, Play, RefreshCw } from 'lucide-react';
import { runBacktest, getBacktestYears } from '../api/client';
import { formatCurrency, formatPct } from '../utils/format';
import StatCard from './common/StatCard';

export default function BacktestPanel() {
  const [availableYears, setAvailableYears] = useState([]);
  const [params, setParams] = useState({
    years: 5,
    strategy: 'value',
    bankroll: 500,
    pool_size: 5000,
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getBacktestYears()
      .then(setAvailableYears)
      .catch(() => setAvailableYears([]));
  }, []);

  const handleRun = async () => {
    setLoading(true);
    try {
      const data = await runBacktest(params);
      setResults(data);
    } catch (err) {
      console.error('Backtest failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Config */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <History className="w-4 h-4 text-gold" />
          Backtest Configuration
        </h2>

        {availableYears.length > 0 && (
          <div className="text-xs text-gray-500 mb-3">
            Available years: {availableYears.join(', ')}
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Years
            </label>
            <input
              type="number"
              value={params.years}
              onChange={(e) =>
                setParams({ ...params, years: Number(e.target.value) })
              }
              min="1"
              max="20"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Strategy
            </label>
            <select
              value={params.strategy}
              onChange={(e) =>
                setParams({ ...params, strategy: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            >
              <option value="value">Value-Based</option>
              <option value="anti_consensus">Anti-Consensus</option>
              <option value="balanced">Balanced</option>
              <option value="favorites">Favorites Only</option>
              <option value="longshots">Longshots Only</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Bankroll ($)
            </label>
            <input
              type="number"
              value={params.bankroll}
              onChange={(e) =>
                setParams({ ...params, bankroll: Number(e.target.value) })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Pool Size ($)
            </label>
            <input
              type="number"
              value={params.pool_size}
              onChange={(e) =>
                setParams({ ...params, pool_size: Number(e.target.value) })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          className="mt-4 flex items-center gap-2 px-5 py-2.5 bg-augusta hover:bg-augusta-light disabled:bg-gray-700 text-white text-sm font-bold rounded-lg transition-colors"
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {loading ? 'Running...' : 'Run Backtest'}
        </button>
      </div>

      {/* Results */}
      {results && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard
              label="Total Return"
              value={formatPct(results.total_return)}
              trend={results.total_return > 0 ? 'up' : 'down'}
              className="border-l-2 border-l-augusta"
            />
            <StatCard
              label="Avg Annual ROI"
              value={formatPct(results.avg_annual_roi)}
              trend={results.avg_annual_roi > 0 ? 'up' : 'down'}
            />
            <StatCard
              label="Win Rate"
              value={formatPct(results.win_rate)}
            />
            <StatCard
              label="Best Year"
              value={formatCurrency(results.best_year)}
              className="border-l-2 border-l-green-500"
            />
            <StatCard
              label="Worst Year"
              value={formatCurrency(results.worst_year)}
              className="border-l-2 border-l-red-500"
            />
          </div>

          {/* Cumulative Returns Chart */}
          {results.yearly_results && (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-4">
                Cumulative Returns
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={results.yearly_results}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="year"
                      tick={{ fontSize: 11, fill: '#9ca3af' }}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: '#6b7280' }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(val, name) => [
                        formatCurrency(val),
                        name === 'cumulative'
                          ? 'Cumulative P/L'
                          : 'Year P/L',
                      ]}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Line
                      type="monotone"
                      dataKey="cumulative"
                      stroke="#006747"
                      strokeWidth={2}
                      dot={{ fill: '#006747', r: 3 }}
                      name="Cumulative P/L"
                    />
                    <Line
                      type="monotone"
                      dataKey="profit"
                      stroke="#FDD835"
                      strokeWidth={1.5}
                      dot={{ fill: '#FDD835', r: 2 }}
                      name="Year P/L"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Year-by-Year Breakdown */}
          {results.yearly_results && (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-4">
                Year-by-Year Breakdown
              </h3>
              <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] uppercase tracking-wider text-gray-600 border-b border-gray-700/50 mb-1">
                <span className="w-16">Year</span>
                <span className="flex-1">Picks</span>
                <span className="w-20 text-right">Invested</span>
                <span className="w-20 text-right">Payout</span>
                <span className="w-20 text-right">Profit</span>
                <span className="w-16 text-right">ROI</span>
              </div>
              <div className="space-y-0.5 max-h-64 overflow-y-auto">
                {results.yearly_results.map((yr, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800/60 text-xs"
                  >
                    <span className="w-16 text-gray-400 font-mono">
                      {yr.year}
                    </span>
                    <span className="flex-1 text-gray-300 truncate">
                      {yr.picks?.join(', ') || '--'}
                    </span>
                    <span className="w-20 text-right text-gray-400 font-mono">
                      {formatCurrency(yr.invested)}
                    </span>
                    <span className="w-20 text-right text-gray-300 font-mono">
                      {formatCurrency(yr.payout)}
                    </span>
                    <span
                      className={`w-20 text-right font-mono font-bold ${
                        yr.profit >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {formatCurrency(yr.profit)}
                    </span>
                    <span
                      className={`w-16 text-right font-mono ${
                        yr.roi >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {formatPct(yr.roi)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!results && !loading && (
        <div className="text-center py-16 text-gray-600">
          <History className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            Configure parameters above and run a backtest to see historical
            performance of different strategies.
          </p>
        </div>
      )}
    </div>
  );
}
