import { useState } from 'react';
import { X, Settings } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';

const PAYOUT_PRESETS = {
  olympic_hills_2026: {
    label: 'Olympic Hills 2026 (40/18/12/9/6/5/3/3/2/1)',
    payouts: {
      '1st': 0.40,
      '2nd': 0.18,
      '3rd': 0.12,
      '4th': 0.09,
      '5th': 0.06,
      '6th': 0.05,
      '7th': 0.03,
      '8th': 0.03,
      '9th': 0.02,
      '10th': 0.01,
    },
  },
  standard: {
    label: 'Standard (50/20/12/5/5 + 1.6% each 6-10)',
    payouts: {
      '1st': 0.50,
      '2nd': 0.20,
      '3rd': 0.12,
      '4th': 0.05,
      '5th': 0.05,
      '6th': 0.016,
      '7th': 0.016,
      '8th': 0.016,
      '9th': 0.016,
      '10th': 0.016,
    },
  },
  deep: {
    label: 'Deep (50/25/15/10)',
    payouts: { '1st': 0.50, '2nd': 0.25, '3rd': 0.15, '4th': 0.10 },
  },
  winner_take_all: {
    label: 'Winner Take All',
    payouts: { '1st': 1.00 },
  },
};

const DEFAULT_BONUSES = {
  round_leader_r1: 1000,
  round_leader_r2: 1000,
  round_leader_r3: 1000,
  low_18: 1000,
  low_27: 1000,
  low_36: 1000,
  last_place_sunday: 200,
};

export default function AuctionConfig({ open, onClose }) {
  const { auction, configure, reset } = useAuction();
  const [poolSize, setPoolSize] = useState(auction?.total_pool || 50000);
  const [bankroll, setBankroll] = useState(auction?.my_bankroll || 12000);
  const [numBidders, setNumBidders] = useState(auction?.num_bidders || 10);
  const [preset, setPreset] = useState('olympic_hills_2026');
  const [bonuses, setBonuses] = useState(
    auction?.bonuses || { ...DEFAULT_BONUSES }
  );
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await configure({
        total_pool: poolSize,
        my_bankroll: bankroll,
        num_bidders: numBidders,
        payout_structure: PAYOUT_PRESETS[preset].payouts,
        bonuses,
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

          {/* Bonuses */}
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-2">
              Fixed Bonuses ($)
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                ['round_leader_r1', 'R1 Leader'],
                ['round_leader_r2', 'R2 Leader'],
                ['round_leader_r3', 'R3 Leader'],
                ['low_18', 'Low 18'],
                ['low_27', 'Low 27'],
                ['low_36', 'Low 36'],
                ['last_place_sunday', 'Last Place Sun'],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 w-20 shrink-0">
                    {label}
                  </span>
                  <input
                    type="number"
                    value={bonuses[key] || 0}
                    onChange={(e) =>
                      setBonuses((prev) => ({
                        ...prev,
                        [key]: Number(e.target.value),
                      }))
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white focus:border-augusta focus:outline-none"
                  />
                </div>
              ))}
            </div>
            <p className="text-[9px] text-gray-600 mt-1">
              Total: ${Object.values(bonuses).reduce((a, b) => a + b, 0).toLocaleString()}
            </p>
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
