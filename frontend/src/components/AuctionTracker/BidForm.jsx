import { useState, useEffect, useMemo } from 'react';
import clsx from 'clsx';
import { DollarSign, User, Search } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { formatCurrency, formatPct } from '../../utils/format';

export default function BidForm({ preselectedGolfer, onClearPreselect }) {
  const { golfers, auction, recordBid } = useAuction();
  const [search, setSearch] = useState('');
  const [selectedGolferId, setSelectedGolferId] = useState(
    preselectedGolfer?.id || ''
  );
  const [buyer, setBuyer] = useState('');
  const [price, setPrice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  // Sync preselected golfer (side effect, not memoized value)
  useEffect(() => {
    if (preselectedGolfer?.id) {
      setSelectedGolferId(preselectedGolfer.id);
      setSearch(preselectedGolfer.name || '');
    }
  }, [preselectedGolfer]);

  const remaining = useMemo(() => {
    const soldIds = new Set(auction?.golfers_sold || []);
    return golfers.filter((g) => !soldIds.has(g.id));
  }, [golfers, auction?.golfers_sold]);

  const filtered = useMemo(() => {
    if (!search) return remaining;
    const q = search.toLowerCase();
    return remaining.filter((g) => g.name?.toLowerCase().includes(q));
  }, [remaining, search]);

  const selectedGolfer = golfers.find((g) => g.id === selectedGolferId);

  const priceNum = parseFloat(price) || 0;
  // Use ev_score as the model's dollar EV estimate
  const modelValue = selectedGolfer?.ev_score ?? null;
  const isUnderValue = modelValue != null && priceNum > 0 && priceNum < modelValue;
  const isOverValue = modelValue != null && priceNum > 0 && priceNum >= modelValue;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedGolferId || !buyer || !priceNum) return;
    setSubmitting(true);
    try {
      await recordBid({
        golfer_id: selectedGolferId,
        buyer: buyer,
        price: priceNum,
      });
      setSearch('');
      setSelectedGolferId('');
      setBuyer('');
      setPrice('');
      onClearPreselect?.();
    } catch (err) {
      console.error('Bid failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const selectGolfer = (g) => {
    setSelectedGolferId(g.id);
    setSearch(g.name);
    setShowDropdown(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Golfer Search / Select */}
      <div className="relative">
        <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
          Golfer
        </label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setSelectedGolferId('');
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            placeholder="Search golfer..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
          />
        </div>
        {showDropdown && !selectedGolferId && (
          <div className="absolute z-20 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-48 overflow-y-auto">
            {filtered.slice(0, 20).map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => selectGolfer(g)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-augusta/20 text-gray-300 hover:text-white flex items-center justify-between"
              >
                <span>
                  <span className="text-gray-500 font-mono mr-2 text-xs">
                    {g.world_ranking}
                  </span>
                  {g.name}
                </span>
                <span className="text-xs text-gray-500">
                  {formatPct(g.model_win_prob)}
                </span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-500">
                No golfers found
              </div>
            )}
          </div>
        )}
      </div>

      {/* Model Value Indicator */}
      {selectedGolfer && (
        <div className="flex items-center gap-3 text-xs bg-gray-800/60 rounded px-3 py-2 border border-gray-700/50">
          <span className="text-gray-500">Model Value:</span>
          <span className="font-bold text-gold">
            {modelValue != null ? formatCurrency(modelValue) : '--'}
          </span>
          <span className="text-gray-600">|</span>
          <span className="text-gray-500">Win%:</span>
          <span className="text-green-400 font-mono">
            {formatPct(selectedGolfer.model_win_prob)}
          </span>
          <span className="text-gray-600">|</span>
          <span className="text-gray-500">EV:</span>
          <span className="text-green-300 font-mono">
            {selectedGolfer.ev_score?.toFixed(2) || '--'}
          </span>
        </div>
      )}

      {/* Buyer + Price Row */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Buyer
          </label>
          <div className="flex gap-1">
            <div className="relative flex-1">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                value={buyer}
                onChange={(e) => setBuyer(e.target.value)}
                placeholder="Buyer name..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
              />
            </div>
            <button
              type="button"
              onClick={() => setBuyer('Me')}
              className="px-3 py-2 bg-augusta/30 hover:bg-augusta/50 text-gold text-xs font-bold rounded-lg border border-augusta/40 transition-colors shrink-0"
            >
              ME
            </button>
          </div>
        </div>

        <div className="w-36">
          <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Price
          </label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0"
              min="0"
              step="5"
              className={clsx(
                'w-full bg-gray-800 border rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:ring-1',
                isUnderValue
                  ? 'border-green-500/60 focus:border-green-500 focus:ring-green-500 glow-green'
                  : isOverValue
                    ? 'border-red-500/60 focus:border-red-500 focus:ring-red-500 glow-red'
                    : 'border-gray-700 focus:border-augusta focus:ring-augusta'
              )}
            />
          </div>
        </div>
      </div>

      {/* Price vs Value Feedback */}
      {priceNum > 0 && modelValue != null && (
        <div
          className={clsx(
            'text-xs px-3 py-1 rounded',
            isUnderValue
              ? 'text-green-400 bg-green-500/10'
              : 'text-red-400 bg-red-500/10'
          )}
        >
          {isUnderValue
            ? `Under model value by ${formatCurrency(modelValue - priceNum)} - good deal`
            : `Over model value by ${formatCurrency(priceNum - modelValue)} - overpaying`}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!selectedGolferId || !buyer || !priceNum || submitting}
        className="w-full py-2.5 bg-augusta hover:bg-augusta-light disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold text-sm rounded-lg transition-colors"
      >
        {submitting ? 'Recording...' : 'Record Bid'}
      </button>
    </form>
  );
}
