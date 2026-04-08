import clsx from 'clsx';
import { Zap } from 'lucide-react';
import AlertBadge from './AlertBadge';
import { formatCurrency, formatPct, evColor } from '../../utils/format';

export default function GolferRow({ golfer, onQuickBid, compact = false }) {
  if (!golfer) return null;

  return (
    <div
      className={clsx(
        'flex items-center gap-2 px-3 py-2 hover:bg-gray-800/60 rounded transition-colors group',
        compact ? 'text-xs' : 'text-sm'
      )}
    >
      {/* Rank */}
      <span className="w-8 text-right text-gray-500 font-mono text-xs">
        {golfer.rank || '--'}
      </span>

      {/* Name */}
      <span className="flex-1 font-medium text-white truncate min-w-0">
        {golfer.name}
      </span>

      {/* Odds */}
      {!compact && (
        <span className="w-16 text-right text-gray-400 font-mono text-xs">
          {golfer.odds || '--'}
        </span>
      )}

      {/* Model Win% */}
      <span className="w-14 text-right text-gray-300 font-mono text-xs">
        {formatPct(golfer.model_win_pct)}
      </span>

      {/* EV */}
      <span
        className={clsx(
          'w-12 text-right font-mono text-xs font-bold',
          evColor(golfer.ev)
        )}
      >
        {golfer.ev != null ? golfer.ev.toFixed(1) : '--'}
      </span>

      {/* Alert */}
      <div className="w-16 flex justify-center">
        {golfer.alert_level && <AlertBadge level={golfer.alert_level} />}
      </div>

      {/* Quick Bid */}
      {onQuickBid && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onQuickBid(golfer);
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-augusta/20 hover:bg-augusta/40 text-gold"
          title="Quick bid"
        >
          <Zap className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}
