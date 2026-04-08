import clsx from 'clsx';
import { Undo2 } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { formatCurrency } from '../../utils/format';

export default function BidHistory() {
  const { bidHistory, golfers, undoLastBid } = useAuction();
  const bids = bidHistory || [];
  const recent = [...bids].reverse().slice(0, 10);

  // Helper to find golfer name from ID
  const getGolferName = (golferId) => {
    const golfer = golfers.find((g) => g.id === golferId);
    return golfer?.name || `Golfer #${golferId}`;
  };

  if (!recent.length) {
    return (
      <div className="text-center py-6 text-gray-600 text-sm">
        No bids recorded yet
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">
          Recent Bids
        </h3>
        {bids.length > 0 && (
          <button
            onClick={undoLastBid}
            className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-red-400 transition-colors"
            title="Undo last bid"
          >
            <Undo2 className="w-3 h-3" />
            Undo Last
          </button>
        )}
      </div>
      <div className="max-h-64 overflow-y-auto space-y-1">
        {recent.map((bid, i) => {
          return (
            <div
              key={i}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded text-xs',
                i === 0 ? 'bg-gray-800/80 border border-gray-700/50' : 'bg-gray-800/40'
              )}
            >
              <span className="text-gray-500 font-mono w-5">
                {bids.length - i}
              </span>
              <span className="flex-1 text-white font-medium truncate">
                {getGolferName(bid.golfer_id)}
              </span>
              <span className="text-gray-400 truncate max-w-[80px]">
                {bid.buyer}
              </span>
              <span className="font-mono font-bold text-gray-300">
                {formatCurrency(bid.price)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
