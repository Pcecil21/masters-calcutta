import { useState, useEffect } from 'react';
import { Layers, RefreshCw } from 'lucide-react';
import { getFieldValue } from '../../api/client';
import { formatCurrency, formatPct } from '../../utils/format';

export default function FieldValue() {
  const [field, setField] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchField = async () => {
    try {
      const data = await getFieldValue();
      setField(data);
    } catch {
      // Silently handle - card just won't display
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchField();
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800/50 border border-gold/30 rounded-xl p-4 flex items-center justify-center h-32">
        <RefreshCw className="w-4 h-4 text-gold animate-spin" />
      </div>
    );
  }

  if (!field) return null;

  return (
    <div className="bg-gray-800/50 border border-gold/30 rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="w-4 h-4 text-gold" />
        <h3 className="text-sm font-black text-gold uppercase tracking-wider">
          The Field
        </h3>
        <span className="text-[10px] text-gray-500 ml-auto">
          All unsold golfers combined
        </span>
      </div>

      {/* Key Stats Row */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
            Win%
          </div>
          <div className="text-xs font-mono font-bold text-white">
            {formatPct(field.combined_win_pct)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
            Top 5%
          </div>
          <div className="text-xs font-mono font-bold text-white">
            {formatPct(field.combined_top5_pct)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
            Top 10%
          </div>
          <div className="text-xs font-mono font-bold text-white">
            {formatPct(field.combined_top10_pct)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
            Golfers
          </div>
          <div className="text-xs font-mono font-bold text-white">
            {field.golfer_count || '--'}
          </div>
        </div>
      </div>

      {/* EV and Max Bid */}
      <div className="grid grid-cols-2 gap-3 mb-2">
        <div className="bg-gray-900/60 rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            Combined EV
          </div>
          <div className="text-2xl font-black text-gold font-mono">
            {formatCurrency(field.combined_ev)}
          </div>
        </div>
        <div className="bg-gray-900/60 rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            Max Bid for Field
          </div>
          <div className="text-2xl font-black text-green-400 font-mono">
            {formatCurrency(field.max_bid)}
          </div>
        </div>
      </div>

      <p className="text-[11px] text-gray-500 text-center italic">
        If the Field goes for less than{' '}
        <span className="text-green-400 font-medium">
          {formatCurrency(field.max_bid)}
        </span>
        , it's a steal
      </p>
    </div>
  );
}
