/**
 * Format a number as USD currency.
 */
export function formatCurrency(value, decimals = 0) {
  if (value == null || isNaN(value)) return '$--';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a decimal as a percentage string (e.g., 0.1234 -> "12.3%").
 */
export function formatPct(value, decimals = 1) {
  if (value == null || isNaN(value)) return '--%';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a number that is already a percentage (e.g., 12.34 -> "12.3%").
 */
export function formatPctRaw(value, decimals = 1) {
  if (value == null || isNaN(value)) return '--%';
  return `${Number(value).toFixed(decimals)}%`;
}

/**
 * Format a multiplier (e.g., 1.5 -> "1.5x").
 */
export function formatMultiplier(value, decimals = 1) {
  if (value == null || isNaN(value)) return '--x';
  return `${Number(value).toFixed(decimals)}x`;
}

/**
 * Return a Tailwind text color class based on EV value.
 */
export function evColor(ev) {
  if (ev == null) return 'text-gray-400';
  if (ev >= 2.0) return 'text-green-400';
  if (ev >= 1.5) return 'text-green-300';
  if (ev >= 1.0) return 'text-yellow-300';
  if (ev >= 0.5) return 'text-orange-400';
  return 'text-red-400';
}

/**
 * Return a Tailwind text color class based on value comparison.
 */
export function valueCompareColor(price, modelValue) {
  if (price == null || modelValue == null) return 'text-gray-400';
  const ratio = price / modelValue;
  if (ratio < 0.8) return 'text-green-400';
  if (ratio < 1.0) return 'text-green-300';
  if (ratio < 1.2) return 'text-yellow-300';
  return 'text-red-400';
}

/**
 * Return alert-level color classes.
 */
export function alertColor(level) {
  switch (level) {
    case 'MUST_BID':
      return 'bg-red-500/20 text-red-400 border-red-500/50';
    case 'STRONG_VALUE':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
    case 'GOOD_VALUE':
      return 'bg-green-500/20 text-green-400 border-green-500/50';
    case 'FAIR':
      return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
    case 'OVERPRICED':
      return 'bg-red-500/20 text-red-500 border-red-500/50';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
  }
}
