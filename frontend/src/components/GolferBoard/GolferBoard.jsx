import { useState, useMemo } from 'react';
import { Search, ChevronUp, ChevronDown, Filter } from 'lucide-react';
import clsx from 'clsx';
import { useAuction } from '../../hooks/useAuction';
import { formatPct, evColor } from '../../utils/format';
import AlertBadge from '../common/AlertBadge';
import GolferDetail from './GolferDetail';

const COLUMNS = [
  { key: 'rank', label: 'Rank', width: 'w-14', align: 'text-right' },
  { key: 'name', label: 'Name', width: 'flex-1', align: 'text-left' },
  { key: 'world_ranking', label: 'World', width: 'w-16', align: 'text-right' },
  { key: 'odds', label: 'Odds', width: 'w-20', align: 'text-right' },
  {
    key: 'model_win_pct',
    label: 'Win%',
    width: 'w-16',
    align: 'text-right',
    format: formatPct,
  },
  {
    key: 'model_top5_pct',
    label: 'Top5%',
    width: 'w-16',
    align: 'text-right',
    format: formatPct,
  },
  {
    key: 'model_top10_pct',
    label: 'Top10%',
    width: 'w-16',
    align: 'text-right',
    format: formatPct,
  },
  {
    key: 'anti_consensus_score',
    label: 'AC Score',
    width: 'w-18',
    align: 'text-right',
    format: (v) => (v != null ? v.toFixed(2) : '--'),
  },
  { key: 'alert_level', label: 'Alert', width: 'w-20', align: 'text-center' },
];

export default function GolferBoard() {
  const { golfers } = useAuction();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('rank');
  const [sortDir, setSortDir] = useState('asc');
  const [expandedId, setExpandedId] = useState(null);

  const filtered = useMemo(() => {
    let list = [...(golfers || [])];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((g) => g.name?.toLowerCase().includes(q));
    }
    list.sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (av == null) av = sortDir === 'asc' ? Infinity : -Infinity;
      if (bv == null) bv = sortDir === 'asc' ? Infinity : -Infinity;
      if (typeof av === 'string') {
        return sortDir === 'asc'
          ? av.localeCompare(bv)
          : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? av - bv : bv - av;
    });
    return list;
  }, [golfers, search, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  };

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search golfers..."
          className="w-full bg-gray-800/80 border border-gray-700/50 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-augusta focus:outline-none focus:ring-1 focus:ring-augusta"
        />
      </div>

      {/* Table */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-800/80 border-b border-gray-700/50">
          {COLUMNS.map((col) => (
            <button
              key={col.key}
              onClick={() => toggleSort(col.key)}
              className={clsx(
                'text-[10px] uppercase tracking-wider font-medium flex items-center gap-1 transition-colors',
                col.width,
                col.align,
                sortKey === col.key
                  ? 'text-gold'
                  : 'text-gray-500 hover:text-gray-300'
              )}
            >
              {col.label}
              {sortKey === col.key &&
                (sortDir === 'asc' ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                ))}
            </button>
          ))}
        </div>

        {/* Rows */}
        <div className="max-h-[600px] overflow-y-auto divide-y divide-gray-800/50">
          {filtered.map((g) => (
            <div key={g.id}>
              <div
                onClick={() =>
                  setExpandedId(expandedId === g.id ? null : g.id)
                }
                className="flex items-center gap-2 px-4 py-2 hover:bg-augusta/5 cursor-pointer transition-colors text-sm"
              >
                <span className="w-14 text-right text-gray-500 font-mono text-xs">
                  {g.rank || '--'}
                </span>
                <span className="flex-1 text-white font-medium truncate">
                  {g.name}
                </span>
                <span className="w-16 text-right text-gray-400 font-mono text-xs">
                  {g.world_ranking || '--'}
                </span>
                <span className="w-20 text-right text-gray-400 font-mono text-xs">
                  {g.odds || '--'}
                </span>
                <span className="w-16 text-right text-green-400 font-mono text-xs">
                  {formatPct(g.model_win_pct)}
                </span>
                <span className="w-16 text-right text-green-300 font-mono text-xs">
                  {formatPct(g.model_top5_pct)}
                </span>
                <span className="w-16 text-right text-yellow-300 font-mono text-xs">
                  {formatPct(g.model_top10_pct)}
                </span>
                <span className="w-18 text-right text-gray-300 font-mono text-xs">
                  {g.anti_consensus_score?.toFixed(2) || '--'}
                </span>
                <div className="w-20 flex justify-center">
                  {g.alert_level && <AlertBadge level={g.alert_level} />}
                </div>
              </div>

              {/* Expanded Detail */}
              {expandedId === g.id && (
                <div className="px-4 pb-4">
                  <GolferDetail
                    golferId={g.id}
                    onClose={() => setExpandedId(null)}
                  />
                </div>
              )}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-8 text-gray-600 text-sm">
              No golfers match your search
            </div>
          )}
        </div>
      </div>

      <div className="text-xs text-gray-600 text-right">
        {filtered.length} golfers shown
      </div>
    </div>
  );
}
