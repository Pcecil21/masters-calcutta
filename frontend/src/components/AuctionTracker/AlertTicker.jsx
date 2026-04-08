import { useMemo } from 'react';
import clsx from 'clsx';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { formatCurrency } from '../../utils/format';

export default function AlertTicker() {
  const { alerts } = useAuction();

  const highPriority = useMemo(
    () =>
      (alerts || []).filter(
        (a) => a.priority === 'high' || a.priority === 'critical' || a.alert_type === 'must_bid' || a.alert_type === 'strong_value'
      ),
    [alerts]
  );

  if (!highPriority.length) return null;

  return (
    <div className="relative overflow-hidden bg-gray-800/60 border border-gray-700/40 rounded-lg h-10">
      <div className="absolute inset-y-0 left-0 w-8 bg-gradient-to-r from-gray-800/60 to-transparent z-10" />
      <div className="absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-gray-800/60 to-transparent z-10" />
      <div className="flex items-center h-full whitespace-nowrap animate-[scroll-left_30s_linear_infinite]">
        {highPriority.map((alert, i) => (
          <span key={i} className="inline-flex items-center gap-2 mx-6">
            {alert.alert_type === 'must_bid' || alert.priority === 'critical' ? (
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 animate-pulse" />
            ) : (
              <TrendingUp className="w-3.5 h-3.5 text-orange-400" />
            )}
            <span
              className={clsx(
                'text-xs font-bold',
                alert.alert_type === 'must_bid' || alert.priority === 'critical'
                  ? 'text-red-400'
                  : 'text-orange-400'
              )}
            >
              {alert.message}
            </span>
            {alert.recommended_max != null && (
              <span className="text-[10px] text-gray-500">
                max {formatCurrency(alert.recommended_max)}
              </span>
            )}
            {alert.current_price != null && (
              <span className="text-[10px] text-gold font-mono">
                @ {formatCurrency(alert.current_price)}
              </span>
            )}
          </span>
        ))}
        {/* Duplicate for seamless scroll */}
        {highPriority.map((alert, i) => (
          <span
            key={`dup-${i}`}
            className="inline-flex items-center gap-2 mx-6"
          >
            {alert.alert_type === 'must_bid' || alert.priority === 'critical' ? (
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 animate-pulse" />
            ) : (
              <TrendingUp className="w-3.5 h-3.5 text-orange-400" />
            )}
            <span
              className={clsx(
                'text-xs font-bold',
                alert.alert_type === 'must_bid' || alert.priority === 'critical'
                  ? 'text-red-400'
                  : 'text-orange-400'
              )}
            >
              {alert.message}
            </span>
            {alert.recommended_max != null && (
              <span className="text-[10px] text-gray-500">
                max {formatCurrency(alert.recommended_max)}
              </span>
            )}
            {alert.current_price != null && (
              <span className="text-[10px] text-gold font-mono">
                @ {formatCurrency(alert.current_price)}
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
