import { useState } from 'react';
import { X, Settings } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';

const PAYOUT_PRESETS = {
  standard: {
    label: 'Standard (70/20/10)',
    payouts: { '1st': 70, '2nd': 20, '3rd': 10 },
  },
  deep: {
    label: 'Deep (50/25/15/10)',
    payouts: { '1st': 50, '2nd': 25, '3rd': 15, '4th': 10 },
  },
  flat: {
    label: 'Flat Top 5',
    payouts: { '1st': 40, '2nd': 25, '3rd': 15, '4th': 12, '5th': 8 },
  },
  winner_take_all: {
    label: 'Winner Take All',
    payouts: { '1st': 100 },
  },
};

export default function AuctionConfig({ open, onClose }) {
  const { auction, configure, reset } = useAuction();
  const [poolSize, setPoolSize] = useState(auction?.pool_size || 5000);
  const [bankroll, setBankroll] = useState(auction?.bankroll || 500);
  const [numBidders, setNumBidders] = useState(auction?.num_bidders || 10);
  const [preset, setPreset] = useState('standard');
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await configure({
        pool_size: poolSize,
        bankroll: bankroll,
        num_bidders: numBidders,
        payout_structure: PAYOUT_PRESETS[preset].payouts,
      });
      onClose();
    } catch (err) {
      console.error('Config failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (window.confirm('Reset all auction data? This cannot be undone.')) {
      await reset();
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md mx-4 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-gold" />
            <h2 className="text-sm font-bold text-white">
              Auction Configuration
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-800 rounded transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Total Pool Size ($)
            </label>
            <input
              type="number"
              value={poolSize}
              onChange={(e) => setPoolSize(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              My Bankroll ($)
            </label>
            <input
              type="number"
              value={bankroll}
              onChange={(e) => setBankroll(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Number of Bidders
            </label>
            <input
              type="number"
              value={numBidders}
              onChange={(e) => setNumBidders(Number(e.target.value))}
              min="2"
              max="50"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-augusta focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Payout Structure
            </label>
            <div className="space-y-2">
              {Object.entries(PAYOUT_PRESETS).map(([key, val]) => (
                <label
                  key={key}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                    preset === key
                      ? 'border-augusta bg-augusta/10 text-white'
                      : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <input
                    type="radio"
                    name="preset"
                    value={key}
                    checked={preset === key}
                    onChange={() => setPreset(key)}
                    className="sr-only"
                  />
                  <span className="text-sm">{val.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-800">
          <button
            onClick={handleReset}
            className="text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            Reset Auction
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-augusta hover:bg-augusta-light text-white text-xs font-bold rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Config'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
