import { useRef } from 'react';
import { X, Printer, Copy } from 'lucide-react';
import { useAuction } from '../../hooks/useAuction';
import { formatCurrency, formatPct } from '../../utils/format';

export default function ShareCard({ portfolio, onClose }) {
  const { golfers } = useAuction();
  const cardRef = useRef(null);

  const entries = portfolio?.entries || [];
  const totalInvested = portfolio?.total_invested || 0;
  const totalEV = portfolio?.total_expected_value || 0;
  const expectedROI = portfolio?.expected_roi || 0;
  const riskScore = portfolio?.risk_score;

  const getGolferName = (golferId) => {
    const g = golfers.find((gl) => gl.id === golferId);
    return g?.name || `Golfer #${golferId}`;
  };

  const handlePrint = () => {
    window.print();
  };

  const handleCopy = async () => {
    // Build a text representation for clipboard
    const lines = [
      'MY MASTERS CALCUTTA PORTFOLIO',
      '================================',
      '',
      ...entries.map((e) => {
        const name = getGolferName(e.golfer_id);
        const evMult = e.ev_multiple != null ? `${e.ev_multiple.toFixed(1)}x` : '--';
        return `${name.padEnd(20)} ${formatCurrency(e.purchase_price).padStart(8)}  EV: ${evMult}`;
      }),
      '',
      '--------------------------------',
      `Total Invested:  ${formatCurrency(totalInvested)}`,
      `Expected Value:  ${formatCurrency(totalEV)}`,
      `Expected ROI:    ${formatPct(expectedROI)}`,
      `Risk Score:      ${riskScore != null ? riskScore.toFixed(1) : '--'}`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
    } catch {
      // fallback: select text
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center overflow-auto print:bg-white print:relative print:inset-auto">
      <div className="mx-4 my-8">
        {/* Controls - hide on print */}
        <div className="flex items-center justify-end gap-2 mb-3 print:hidden">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-300 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            Copy
          </button>
          <button
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-300 transition-colors"
          >
            <Printer className="w-3.5 h-3.5" />
            Print
          </button>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* The Card */}
        <div
          ref={cardRef}
          className="w-[400px] bg-gray-900 rounded-xl overflow-hidden shadow-2xl border border-gray-700 print:shadow-none print:border print:border-gray-300"
        >
          {/* Masters Green Header */}
          <div className="bg-augusta px-5 py-4">
            <h2 className="text-white font-black text-sm uppercase tracking-wider text-center">
              My Masters Calcutta Portfolio
            </h2>
            <p className="text-augusta-light text-[10px] text-center mt-0.5 tracking-wider opacity-80">
              Masters 2026
            </p>
          </div>

          {/* Holdings */}
          <div className="px-5 py-4 space-y-0.5">
            {entries.length === 0 ? (
              <p className="text-gray-500 text-xs text-center py-4">No holdings yet</p>
            ) : (
              entries.map((e, i) => {
                const evMult = e.ev_multiple;
                const isPositive = evMult != null && evMult >= 1;
                return (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-white text-sm font-medium truncate block">
                        {getGolferName(e.golfer_id)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400 font-mono text-xs">
                        {formatCurrency(e.purchase_price)}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                          isPositive
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}
                      >
                        {evMult != null ? `${evMult.toFixed(1)}x` : '--'}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Summary Footer */}
          <div className="bg-gray-950 px-5 py-4 grid grid-cols-2 gap-3">
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Total Invested
              </span>
              <span className="text-white font-bold font-mono text-sm">
                {formatCurrency(totalInvested)}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Expected Value
              </span>
              <span className="text-gold font-bold font-mono text-sm">
                {formatCurrency(totalEV)}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Expected ROI
              </span>
              <span
                className={`font-bold font-mono text-sm ${
                  expectedROI > 0 ? 'text-green-400' : expectedROI < 0 ? 'text-red-400' : 'text-gray-400'
                }`}
              >
                {formatPct(expectedROI)}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-gray-500 uppercase tracking-wider block">
                Risk Score
              </span>
              <span className="text-white font-bold font-mono text-sm">
                {riskScore != null ? riskScore.toFixed(1) : '--'}
              </span>
            </div>
          </div>

          {/* Branding Footer */}
          <div className="bg-gray-950 border-t border-gray-800 px-5 py-2 text-center">
            <span className="text-[9px] text-gray-600 uppercase tracking-widest">
              Masters Calcutta Engine
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
