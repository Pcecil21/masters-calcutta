export default function LiveModeToggle({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-green-600 hover:bg-green-500 shadow-lg shadow-green-600/30 flex items-center justify-center transition-all group"
      aria-label="Open Live Auction Mode (press L)"
      title="Live Auction Mode (L)"
    >
      <span className="absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-40 animate-ping" />
      <span className="relative text-white font-black text-xs tracking-wider">
        LIVE
      </span>
    </button>
  );
}
