import { useState, useMemo } from 'react';
import {
  Trophy,
  Calculator,
  TrendingUp,
  TrendingDown,
  Target,
  Brain,
  Lightbulb,
  RefreshCw,
  X,
} from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { calculateScorecard } from '../../api/client';
import { formatCurrency, formatPct } from '../../utils/format';
import StatCard from '../common/StatCard';

const POSITIONS = Array.from({ length: 10 }, (_, i) => i + 1);
const POSITION_LABELS = {
  1: '1st (Winner)',
  2: '2nd',
  3: '3rd',
  4: '4th',
  5: '5th',
  6: '6th',
  7: '7th',
  8: '8th',
  9: '9th',
  10: '10th',
};

export default function ScorecardPanel() {
  const { golfers } = useAuction();
  const [results, setResults] = useState(
    POSITIONS.map((pos) => ({ finish_position: pos, golfer_name: '' }))
  );
  const [missedCut, setMissedCut] = useState([]);
  const [missedCutInput, setMissedCutInput] = useState('');
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Autocomplete suggestions
  const golferNames = useMemo(
    () => golfers.map((g) => g.name).sort(),
    [golfers]
  );
  const [activeSuggest, setActiveSuggest] = useState(null);

  const updateResult = (index, name) => {
    setResults((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], golfer_name: name };
      return next;
    });
  };

  const getSuggestions = (query) => {
    if (!query || query.length < 2) return [];
    const lower = query.toLowerCase();
    return golferNames.filter((n) => n.toLowerCase().includes(lower)).slice(0, 6);
  };

  const addMissedCut = (name) => {
    if (name && !missedCut.includes(name)) {
      setMissedCut((prev) => [...prev, name]);
    }
    setMissedCutInput('');
  };

  const removeMissedCut = (name) => {
    setMissedCut((prev) => prev.filter((n) => n !== name));
  };

  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    try {
      const filledResults = results
        .filter((r) => r.golfer_name.trim())
        .map((r) => ({
          golfer_name: r.golfer_name.trim(),
          finish_position: r.finish_position,
        }));
      const missedCutResults = missedCut.map((name) => ({
        golfer_name: name,
        finish_position: 'MC',
      }));
      const data = await calculateScorecard([...filledResults, ...missedCutResults]);
      setScorecard(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to calculate scorecard');
    } finally {
      setLoading(false);
    }
  };

  const myGolfers = scorecard?.my_golfers || [];
  const summary = scorecard?.summary || {};
  const accuracy = scorecard?.model_accuracy || {};
  const hindsight = scorecard?.optimal_hindsight || {};
  const bestPick = myGolfers.reduce(
    (best, g) => (!best || (g.profit || 0) > (best.profit || 0) ? g : best),
    null
  );
  const worstPick = myGolfers.reduce(
    (worst, g) => (!worst || (g.profit || 0) < (worst.profit || 0) ? g : worst),
    null
  );

  return (
    <div className="space-y-6">
      {/* Results Entry Form */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <Trophy className="w-4 h-4 text-gold" />
          Enter Tournament Results
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          {POSITIONS.map((pos, idx) => (
            <div key={pos} className="relative">
              <label className="text-[10px] uppercase tracking-wider text-gray-500 mb-1 block">
                {POSITION_LABELS[pos]}
              </label>
              <input
                type="text"
                value={results[idx].golfer_name}
                onChange={(e) => {
                  updateResult(idx, e.target.value);
                  setActiveSuggest(idx);
                }}
                onFocus={() => setActiveSuggest(idx)}
                onBlur={() => setTimeout(() => setActiveSuggest(null), 200)}
                placeholder="Golfer name..."
                className="w-full bg-gray-900/60 border border-gray-700/50 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-augusta/60 transition-colors"
              />
              {activeSuggest === idx &&
                getSuggestions(results[idx].golfer_name).length > 0 && (
                  <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-40 overflow-y-auto">
                    {getSuggestions(results[idx].golfer_name).map((name) => (
                      <button
                        key={name}
                        onMouseDown={() => {
                          updateResult(idx, name);
                          setActiveSuggest(null);
                        }}
                        className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-augusta/20 hover:text-white transition-colors"
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                )}
            </div>
          ))}
        </div>

        {/* Missed Cut Selection */}
        <div className="mb-4">
          <label className="text-[10px] uppercase tracking-wider text-gray-500 mb-1 block">
            Missed Cut (from your portfolio)
          </label>
          <div className="flex gap-2 mb-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={missedCutInput}
                onChange={(e) => setMissedCutInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    addMissedCut(missedCutInput);
                  }
                }}
                placeholder="Add golfer who missed the cut..."
                className="w-full bg-gray-900/60 border border-gray-700/50 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-augusta/60 transition-colors"
              />
              {missedCutInput.length >= 2 && (
                <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-40 overflow-y-auto">
                  {getSuggestions(missedCutInput).map((name) => (
                    <button
                      key={name}
                      onMouseDown={() => addMissedCut(name)}
                      className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-augusta/20 hover:text-white transition-colors"
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          {missedCut.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {missedCut.map((name) => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-red-500/20 text-red-400 border border-red-500/30 rounded text-xs"
                >
                  {name}
                  <button
                    onClick={() => removeMissedCut(name)}
                    className="hover:text-red-300"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={handleCalculate}
          disabled={loading || results.every((r) => !r.golfer_name.trim())}
          className="flex items-center gap-2 px-4 py-2 bg-augusta hover:bg-augusta/80 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Calculator className="w-4 h-4" />
          )}
          Calculate Scorecard
        </button>

        {error && (
          <div className="mt-3 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
            {error}
          </div>
        )}
      </div>

      {/* Scorecard Results */}
      {scorecard && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Total Invested"
              value={formatCurrency(summary.total_invested)}
              className="border-l-2 border-l-gold"
            />
            <StatCard
              label="Total Payout"
              value={formatCurrency(summary.total_payout)}
              trend={summary.total_payout > summary.total_invested ? 'up' : 'down'}
              className="border-l-2 border-l-augusta"
            />
            <StatCard
              label="Net Profit"
              value={formatCurrency(summary.net_profit)}
              trend={summary.net_profit >= 0 ? 'up' : 'down'}
              className={
                summary.net_profit >= 0
                  ? 'border-l-2 border-l-green-500'
                  : 'border-l-2 border-l-red-500'
              }
            />
            <StatCard
              label="ROI"
              value={formatPct(summary.roi)}
              trend={summary.roi >= 0 ? 'up' : 'down'}
              className={
                summary.roi >= 0
                  ? 'border-l-2 border-l-green-500'
                  : 'border-l-2 border-l-red-500'
              }
            />
          </div>

          {/* My Golfers Table */}
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
            <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
              <Trophy className="w-4 h-4 text-gold" />
              My Golfers Performance
            </h2>

            <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] uppercase tracking-wider text-gray-600 border-b border-gray-700/50 mb-1">
              <span className="flex-1">Golfer</span>
              <span className="w-20 text-right">Price Paid</span>
              <span className="w-16 text-right">Finish</span>
              <span className="w-20 text-right">Payout</span>
              <span className="w-20 text-right">Profit/Loss</span>
            </div>
            <div className="space-y-0.5">
              {myGolfers
                .sort((a, b) => {
                  const aPos = typeof a.finish === 'number' ? a.finish : 999;
                  const bPos = typeof b.finish === 'number' ? b.finish : 999;
                  return aPos - bPos;
                })
                .map((g, i) => {
                  const profit = g.profit || 0;
                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-2 px-3 py-2 rounded text-xs transition-colors ${
                        profit > 0
                          ? 'bg-green-500/5 hover:bg-green-500/10'
                          : profit < 0
                            ? 'bg-red-500/5 hover:bg-red-500/10'
                            : 'hover:bg-gray-800/60'
                      }`}
                    >
                      <span className="flex-1 text-white font-medium truncate">
                        {g.name}
                      </span>
                      <span className="w-20 text-right text-gray-300 font-mono">
                        {formatCurrency(g.price_paid)}
                      </span>
                      <span className="w-16 text-right text-gray-400 font-mono">
                        {g.finish === 'MC' ? 'MC' : `T${g.finish}`}
                      </span>
                      <span className="w-20 text-right text-gray-300 font-mono">
                        {formatCurrency(g.payout)}
                      </span>
                      <span
                        className={`w-20 text-right font-mono font-bold ${
                          profit > 0 ? 'text-green-400' : profit < 0 ? 'text-red-400' : 'text-gray-400'
                        }`}
                      >
                        {profit >= 0 ? '+' : ''}
                        {formatCurrency(profit)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Best / Worst Pick */}
          {(bestPick || worstPick) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {bestPick && (
                <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-green-400" />
                    <span className="text-xs font-bold text-green-400 uppercase tracking-wider">
                      Best Pick
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white">{bestPick.name}</div>
                  <div className="text-sm text-green-400 font-mono mt-1">
                    +{formatCurrency(bestPick.profit)} profit
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Paid {formatCurrency(bestPick.price_paid)} | Finished{' '}
                    {bestPick.finish === 'MC' ? 'MC' : `T${bestPick.finish}`}
                  </div>
                </div>
              )}
              {worstPick && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingDown className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                      Worst Pick
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white">{worstPick.name}</div>
                  <div className="text-sm text-red-400 font-mono mt-1">
                    {formatCurrency(worstPick.profit)} loss
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Paid {formatCurrency(worstPick.price_paid)} | Finished{' '}
                    {worstPick.finish === 'MC' ? 'MC' : `T${worstPick.finish}`}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Model Accuracy */}
          {accuracy && Object.keys(accuracy).length > 0 && (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
              <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4 text-gold" />
                Model Accuracy
              </h2>
              <div className="space-y-2 text-xs text-gray-300">
                {accuracy.winner_prediction && (
                  <p>
                    The model predicted{' '}
                    <span className="text-white font-medium">
                      {accuracy.winner_prediction.golfer}
                    </span>{' '}
                    had a{' '}
                    <span className="text-gold font-mono">
                      {formatPct(accuracy.winner_prediction.predicted_prob)}
                    </span>{' '}
                    chance of winning.{' '}
                    {accuracy.winner_prediction.actual_won
                      ? 'He won.'
                      : `${accuracy.winner_prediction.actual_winner} won instead.`}
                  </p>
                )}
                {accuracy.brier_score != null && (
                  <p>
                    Model Brier Score:{' '}
                    <span className="text-gold font-mono font-bold">
                      {accuracy.brier_score.toFixed(4)}
                    </span>
                    <span className="text-gray-500 ml-2">
                      (lower is better, 0 = perfect)
                    </span>
                  </p>
                )}
                {accuracy.calibration && (
                  <p className="text-gray-400 italic">{accuracy.calibration}</p>
                )}
              </div>
            </div>
          )}

          {/* Hindsight Optimal */}
          {hindsight && Object.keys(hindsight).length > 0 && (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-5">
              <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                <Lightbulb className="w-4 h-4 text-gold" />
                Hindsight Optimal
              </h2>
              <p className="text-xs text-gray-400 mb-3">
                With perfect information, the optimal portfolio would have been:
              </p>
              <div className="space-y-1 mb-3">
                {(hindsight.optimal_picks || []).map((pick, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-1.5 bg-gray-900/40 rounded text-xs"
                  >
                    <span className="text-gold font-bold w-5">{i + 1}</span>
                    <span className="flex-1 text-white">{pick.name}</span>
                    <span className="text-gray-400 font-mono">
                      {formatCurrency(pick.price)}
                    </span>
                    <span className="text-green-400 font-mono font-bold">
                      +{formatCurrency(pick.profit)}
                    </span>
                  </div>
                ))}
              </div>
              {hindsight.total_profit != null && (
                <div className="text-sm text-green-400 font-mono font-bold">
                  Optimal total profit: +{formatCurrency(hindsight.total_profit)}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
