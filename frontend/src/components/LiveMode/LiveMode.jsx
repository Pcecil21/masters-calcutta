import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import clsx from 'clsx';
import { X, DollarSign, User, ChevronRight } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { priceCheck } from '../../api/client';
import { formatCurrency, formatPct } from '../../utils/format';

const DEBOUNCE_MS = 200;

export default function LiveMode({ open, onClose }) {
  const { golfers, auction, bidHistory, recordBid, refresh } = useAuction();

  const [search, setSearch] = useState('');
  const [selectedGolferId, setSelectedGolferId] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const [price, setPrice] = useState('');
  const [buyer, setBuyer] = useState('');
  const [verdict, setVerdict] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const searchRef = useRef(null);
  const priceRef = useRef(null);
  const buyerRef = useRef(null);
  const recordRef = useRef(null);
  const debounceTimer = useRef(null);

  // Remaining golfers
  const remaining = useMemo(() => {
    const soldIds = new Set(auction?.golfers_sold || []);
    return golfers.filter((g) => !soldIds.has(g.id));
  }, [golfers, auction?.golfers_sold]);

  // Filtered by search
  const filtered = useMemo(() => {
    if (!search) return remaining;
    const q = search.toLowerCase();
    return remaining.filter((g) => g.name?.toLowerCase().includes(q));
  }, [remaining, search]);

  const selectedGolfer = golfers.find((g) => g.id === selectedGolferId);
  const bankrollRemaining = auction?.remaining_bankroll ?? auction?.my_bankroll ?? 0;
  const golfersLeft = remaining.length;
  const poolSize = auction?.total_pool || 0;
  const bankrollTotal = auction?.my_bankroll || 0;
  const spent = bankrollTotal - bankrollRemaining;

  // Last 3 bids
  const lastBids = bidHistory.slice(-3).reverse();

  // Keyboard: Escape to close
  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  // Focus search on open
  useEffect(() => {
    if (open) {
      setTimeout(() => searchRef.current?.focus(), 100);
    }
  }, [open]);

  // Reset highlight when filtered changes
  useEffect(() => {
    setHighlightIdx(0);
  }, [filtered.length, search]);

  // Debounced price check
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    const priceNum = parseFloat(price);
    if (!selectedGolferId || !priceNum || priceNum <= 0) {
      setVerdict(null);
      return;
    }
    debounceTimer.current = setTimeout(async () => {
      try {
        const data = await priceCheck(selectedGolferId, priceNum);
        setVerdict(data);
      } catch {
        setVerdict(null);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [selectedGolferId, price]);

  const selectGolfer = useCallback((g) => {
    setSelectedGolferId(g.id);
    setSearch(g.name);
    setShowDropdown(false);
    setVerdict(null);
    setPrice('');
    setTimeout(() => priceRef.current?.focus(), 50);
  }, []);

  const handleSearchKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx((prev) => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && filtered.length > 0) {
      e.preventDefault();
      const target = filtered[highlightIdx] || filtered[0];
      if (target) selectGolfer(target);
    } else if (e.key === 'Tab' && selectedGolferId) {
      // natural tab to price
    }
  };

  const handlePriceKeyDown = (e) => {
    if (e.key === 'Tab') {
      // natural tab to buyer
    }
  };

  const handleBuyerKeyDown = (e) => {
    if (e.key === 'Tab') {
      // natural tab to record button
    }
  };

  const handleRecord = async () => {
    const priceNum = parseFloat(price);
    if (!selectedGolferId || !buyer || !priceNum) return;
    setSubmitting(true);
    try {
      await recordBid({
        golfer_id: selectedGolferId,
        buyer,
        price: priceNum,
      });
      // Reset for next golfer
      setSearch('');
      setSelectedGolferId('');
      setPrice('');
      setBuyer('');
      setVerdict(null);
      await refresh();
      setTimeout(() => searchRef.current?.focus(), 50);
    } catch (err) {
      console.error('Live bid failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleRecord();
    }
  };

  if (!open) return null;

  // Verdict display helpers
  const verdictLabel = verdict?.verdict;
  const verdictIsGo = verdictLabel === 'BID';
  const verdictIsMarginal = verdictLabel === 'MARGINAL';
  const verdictIsPass = verdictLabel === 'PASS';

  const maxBid = verdict?.max_bid;
  const breakeven = verdict?.breakeven_price;
  const priceNum = parseFloat(price) || 0;
  const overpaidBy = verdictIsPass && breakeven ? priceNum - breakeven : null;

  return (
    <div
      className="fixed inset-0 z-50 bg-gray-950 flex flex-col"
      role="dialog"
      aria-modal="true"
      aria-label="Live Auction Mode"
    >
      {/* Top Bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
            </span>
            <span className="text-sm font-black text-white uppercase tracking-wider">
              Live Auction Mode
            </span>
          </div>
          <span className="text-xs text-gray-500">|</span>
          <span className="text-sm text-gold font-bold font-mono">
            {formatCurrency(bankrollRemaining)} left
          </span>
          <span className="text-xs text-gray-500">|</span>
          <span className="text-sm text-gray-400">
            {golfersLeft} golfers remaining
          </span>
        </div>
        <button
          onClick={onClose}
          className="flex items-center gap-2 px-3 py-1.5 text-gray-500 hover:text-white transition-colors text-xs"
        >
          <span className="text-gray-600">ESC</span>
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Center Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
        <div className="w-full max-w-2xl space-y-6">
          {/* Golfer Search */}
          <div className="relative">
            <input
              ref={searchRef}
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSelectedGolferId('');
                setShowDropdown(true);
                setVerdict(null);
                setPrice('');
              }}
              onFocus={() => {
                if (!selectedGolferId) setShowDropdown(true);
              }}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              onKeyDown={handleSearchKeyDown}
              placeholder="Type golfer name..."
              className="w-full bg-gray-900 border-2 border-gray-700 rounded-xl px-6 py-4 text-2xl text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-2 focus:ring-augusta/50 font-medium"
              autoComplete="off"
            />
            {showDropdown && !selectedGolferId && filtered.length > 0 && (
              <div className="absolute z-30 w-full mt-2 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl max-h-72 overflow-y-auto">
                {filtered.slice(0, 20).map((g, i) => (
                  <button
                    key={g.id}
                    type="button"
                    onMouseDown={() => selectGolfer(g)}
                    className={clsx(
                      'w-full text-left px-5 py-3 text-lg flex items-center justify-between transition-colors',
                      i === highlightIdx
                        ? 'bg-augusta/20 text-white'
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                    )}
                  >
                    <span>
                      <span className="text-gray-500 font-mono mr-3 text-sm">
                        {g.world_ranking || '--'}
                      </span>
                      {g.name}
                    </span>
                    <span className="text-sm text-green-400 font-mono">
                      {formatPct(g.model_win_prob)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Selected Golfer Info */}
          {selectedGolfer && (
            <div className="text-center space-y-3">
              <h2 className="text-5xl font-bold text-white tracking-tight">
                {selectedGolfer.name}
              </h2>
              <p className="text-2xl text-green-400 font-mono">
                Win Prob: {formatPct(selectedGolfer.model_win_prob)}
              </p>
              {selectedGolfer.ev_score != null && (
                <div className="flex items-center justify-center gap-6">
                  <div>
                    <span className="text-gray-500 text-sm">Max Bid </span>
                    <span className="text-5xl font-bold text-gold font-mono">
                      {formatCurrency(selectedGolfer.ev_score)}
                    </span>
                  </div>
                </div>
              )}

              {/* Price Check Input */}
              <div className="pt-4">
                <div className="relative max-w-xs mx-auto">
                  <DollarSign className="absolute left-4 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-500" />
                  <input
                    ref={priceRef}
                    type="number"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    onKeyDown={handlePriceKeyDown}
                    placeholder="Current price..."
                    min="0"
                    step="5"
                    className="w-full bg-gray-900 border-2 border-gray-700 rounded-xl pl-12 pr-4 py-4 text-3xl text-white text-center placeholder-gray-600 focus:border-gold focus:outline-none focus:ring-2 focus:ring-gold/50 font-mono"
                  />
                </div>
              </div>

              {/* Verdict Display */}
              {verdict && priceNum > 0 && (
                <div className="pt-2 space-y-2">
                  {verdictIsGo && (
                    <div className="animate-pulse">
                      <span className="text-7xl font-black text-green-400 tracking-wider">
                        BID
                      </span>
                      <p className="text-xl text-green-300 mt-1">
                        STEAL at this price
                      </p>
                    </div>
                  )}
                  {verdictIsMarginal && (
                    <div>
                      <span className="text-6xl font-black text-yellow-400 tracking-wider">
                        MARGINAL
                      </span>
                      <p className="text-lg text-yellow-300 mt-1">
                        Slight edge, proceed with caution
                      </p>
                    </div>
                  )}
                  {verdictIsPass && (
                    <div>
                      <span className="text-7xl font-black text-red-500 tracking-wider">
                        PASS
                      </span>
                      <p className="text-lg text-red-300 mt-1">
                        {overpaidBy != null && overpaidBy > 0
                          ? `Overpriced by ${formatCurrency(overpaidBy)}`
                          : 'Overpriced at this level'}
                      </p>
                    </div>
                  )}
                  <div className="flex items-center justify-center gap-6 text-sm text-gray-400 pt-1">
                    {maxBid != null && (
                      <span>
                        Max Bid:{' '}
                        <span className="text-gold font-mono font-bold">
                          {formatCurrency(maxBid)}
                        </span>
                      </span>
                    )}
                    {breakeven != null && (
                      <span>
                        Breakeven:{' '}
                        <span className="text-gray-300 font-mono">
                          {formatCurrency(breakeven)}
                        </span>
                      </span>
                    )}
                    {verdict.ev_multiple != null && (
                      <span>
                        EV:{' '}
                        <span className="text-gray-300 font-mono">
                          {verdict.ev_multiple.toFixed(2)}x
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Quick Record Row */}
              <div className="pt-4 border-t border-gray-800 mt-4">
                <div className="flex items-center gap-3 max-w-lg mx-auto">
                  <div className="flex-1 flex gap-2">
                    <div className="relative flex-1">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                      <input
                        ref={buyerRef}
                        type="text"
                        value={buyer}
                        onChange={(e) => setBuyer(e.target.value)}
                        onKeyDown={handleBuyerKeyDown}
                        placeholder="Buyer..."
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
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
                  <button
                    ref={recordRef}
                    type="button"
                    onClick={handleRecord}
                    onKeyDown={handleRecordKeyDown}
                    disabled={!selectedGolferId || !buyer || !priceNum || submitting}
                    className="px-5 py-2.5 bg-augusta hover:bg-augusta-light disabled:bg-gray-800 disabled:text-gray-600 text-white font-bold text-sm rounded-lg transition-colors flex items-center gap-2"
                  >
                    {submitting ? (
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                    RECORD BID
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="flex items-center justify-between px-6 py-3 border-t border-gray-800 shrink-0 text-xs">
        <div className="flex items-center gap-4">
          {lastBids.length > 0 ? (
            lastBids.map((b, i) => {
              const g = golfers.find((gl) => gl.id === b.golfer_id);
              return (
                <span key={i} className="text-gray-500">
                  {g?.name || `#${b.golfer_id}`}{' '}
                  <span className="text-gray-400 font-mono">
                    {formatCurrency(b.price)}
                  </span>{' '}
                  <span className="text-gray-600">({b.buyer})</span>
                </span>
              );
            })
          ) : (
            <span className="text-gray-600">No bids recorded yet</span>
          )}
        </div>
        <div className="flex items-center gap-4 text-gray-500">
          <span>
            Pool:{' '}
            <span className="text-gray-300 font-mono">{formatCurrency(poolSize)}</span>
          </span>
          <span>
            Spend rate:{' '}
            <span className="text-gray-300 font-mono">
              {formatCurrency(spent)} / {formatCurrency(bankrollTotal)}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
