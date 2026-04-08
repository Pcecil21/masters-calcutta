import clsx from 'clsx';

const config = {
  MUST_BID: {
    label: 'MUST BID',
    classes: 'bg-red-500/20 text-red-400 border-red-500/60 animate-pulse',
  },
  STRONG_VALUE: {
    label: 'STRONG',
    classes: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
  },
  GOOD_VALUE: {
    label: 'GOOD',
    classes: 'bg-green-500/20 text-green-400 border-green-500/50',
  },
  FAIR: {
    label: 'FAIR',
    classes: 'bg-gray-600/30 text-gray-400 border-gray-500/40',
  },
  OVERPRICED: {
    label: 'OVER',
    classes: 'bg-red-500/20 text-red-500 border-red-500/50 line-through',
  },
};

export default function AlertBadge({ level, className }) {
  const c = config[level] || config.FAIR;
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded border',
        c.classes,
        className
      )}
    >
      {c.label}
    </span>
  );
}
