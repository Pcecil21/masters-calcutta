import clsx from 'clsx';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function StatCard({ label, value, trend, subtitle, className }) {
  const trendIcon =
    trend === 'up' ? (
      <TrendingUp className="w-4 h-4 text-green-400" />
    ) : trend === 'down' ? (
      <TrendingDown className="w-4 h-4 text-red-400" />
    ) : trend === 'neutral' ? (
      <Minus className="w-4 h-4 text-gray-500" />
    ) : null;

  return (
    <div
      className={clsx(
        'bg-gray-800/80 border border-gray-700/50 rounded-lg px-4 py-3',
        className
      )}
    >
      <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-1">
        {label}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold text-white">{value}</span>
        {trendIcon}
      </div>
      {subtitle && (
        <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
      )}
    </div>
  );
}
