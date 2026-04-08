import { useState, useMemo, useRef, useCallback } from 'react';
import clsx from 'clsx';
import { Zap, Search, DollarSign, ArrowRight } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { priceCheck } from '../../api/client';
import { formatCurrency, formatMultiplier } from '../../utils/format';

const VERDICT_STYLES = {
  BID: 'bg-green-500/15 border-green-500/40 text-green-400',
  PASS: 'bg-red-500/15 border-red-500/40 text-red-400',
  MARGINAL: 'bg-yellow-500/15 border-yellow-500/40 text-yellow-400',
};

const VERDICT_LABEL_STYLES = {
  BID: 'bg-green-500/30 text-green-300',
  PASS: 'bg-red-500/30 text-red-300',
  MARGINAL: 'bg-yellow-500/30 text-yellow-300',
};

export default function QuickPrice() {
  const { golfers, auction } = useAuction();
  const [search, setSearch] = useState('');
  const [selectedGolferId, setSelectedGolferId] = useState('');
  const [price, setPrice] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);
  const priceRef = useRef(null);

  const remaining = useMemo(() => {
    const soldIds = new Set(auction?.golfers_sold || []);
    return golfers.filter((g) => !soldIds.has(g.id));
  }, [golfers, auction?.golfers_sold]);

  const filtered = useMemo(() => {
    if (!search) return remaining;
    const q = search.toLowerCase();
    return remaining.filter((g) => g.name?.toLowerCase().includes(q));
  }, [remaining, search]);

  const selectGolfer = useCallback((g) => {
    setSelectedGolferId(g.id);
    setSearch(g.name);
    setShowDropdown(false);
    setResult(null);
    // Focus price field immediately for speed
    setTimeout(() => priceRef.current?.focus(), 50);
  }, []);

  const handleCheck = async (e) => {
    e?.preventDefault();
    const priceNum = parseFloat(price);
    if (!selectedGolferId || !priceNum || priceNum <= 0) return;

    setChecking(true);
    setError(null);
    try {
      const data = await priceCheck(selectedGolferId, priceNum);
      setResult(data);
    } catch (err) {
      setError('Check failed');
      setResult(null);
    } finally {
      setChecking(false);
    }
  };

  const handlePriceKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCheck();
    }
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
      <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-gold" />
        Quick Price Check
      </h2>

      <form onSubmit={handleCheck} className="flex items-end gap-2">
        {/* Golfer Search */}
        <div className="flex-1 relative">
          <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Golfer
          </label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSelectedGolferId('');
                setShowDropdown(true);
                setResult(null);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              placeholder="Search..."
              tabIndex={1}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
            />
          </div>
          {showDropdown && !selectedGolferId && (
            <div className="absolute z-30 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-48 overflow-y-auto">
              {filtered.slice(0, 15).map((g) => (
                <button
                  key={g.id}
                  type="button"
                  onMouseDown={() => selectGolfer(g)}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-augusta/20 text-gray-300 hover:text-white flex items-center justify-between"
                >
                  <span>
                    <span className="text-gray-500 font-mono mr-2">{g.world_ranking}</span>
                    {g.name}
                  </span>
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="px-3 py-2 text-xs text-gray-500">No golfers found</div>
              )}
            </div>
          )}
        </div>

        {/* Price Input */}
        <div className="w-28">
          <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Price
          </label>
          <div className="relative">
            <DollarSign className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <input
              ref={priceRef}
              type="number"
              value={price}
              onChange={(e) => {
                setPrice(e.target.value);
                setResult(null);
              }}
              onKeyDown={handlePriceKeyDown}
              placeholder="0"
              min="0"
              step="5"
              tabIndex={2}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
            />
          </div>
        </div>

        {/* Check Button */}
        <button
          type="submit"
          disabled={!selectedGolferId || !parseFloat(price) || checking}
          tabIndex={3}
          className="px-4 py-2 bg-gold/90 hover:bg-gold disabled:bg-gray-700 disabled:text-gray-500 text-gray-900 font-bold text-sm rounded-lg transition-colors shrink-0 flex items-center gap-1.5"
        >
          {checking ? (
            <span className="w-3.5 h-3.5 border-2 border-gray-900/30 border-t-gray-900 rounded-full animate-spin" />
          ) : (
            <ArrowRight className="w-3.5 h-3.5" />
          )}
          CHECK
        </button>
      </form>

      {/* Result */}
      {result && (
        <div
          className={clsx(
            'mt-3 px-4 py-3 rounded-lg border transition-all',
            VERDICT_STYLES[result.verdict] || VERDICT_STYLES.MARGINAL
          )}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span
              className={clsx(
                'text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded',
                VERDICT_LABEL_STYLES[result.verdict] || VERDICT_LABEL_STYLES.MARGINAL
              )}
            >
              {result.verdict}
            </span>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-gray-400">
                EV: <span className="font-mono font-bold text-white">{formatMultiplier(result.ev_multiple)}</span>
              </span>
              <span className="text-gray-400">
                Max Bid: <span className="font-mono font-bold text-white">{formatCurrency(result.max_bid)}</span>
              </span>
            </div>
          </div>
          <p className="text-sm leading-relaxed">{result.message}</p>
        </div>
      )}

      {error && (
        <div className="mt-3 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}
