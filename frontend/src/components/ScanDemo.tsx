import { useEffect, useState } from 'react';

const CAPTIONS = ['Scanning your face…', 'Checking 300+ event photos…', 'Match found in 0.4s'];

// Purely decorative gradient fills standing in for a grid of anonymized event
// photos - the point is the mechanic (scan sweeps the grid, locks onto one
// frame), not a literal screenshot.
const TILE_FILLS = [
  'from-[#8a6d4f] to-[#4a3626]',
  'from-[#5c6b63] to-[#2b332f]',
  'from-[#6d5a72] to-[#332839]',
  'from-[#7a5040] to-[#3a241c]',
  'from-[#4f6a72] to-[#243338]',
  'from-[#836a3f] to-[#3f331d]',
  'from-[#5a5f72] to-[#282b39]',
  'from-[#6f5844] to-[#352a1f]',
];

const TARGET_INDEX = 4;

export default function ScanDemo() {
  const [captionIndex, setCaptionIndex] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setCaptionIndex((prev) => (prev + 1) % CAPTIONS.length);
    }, 2000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <div className="relative mx-auto w-full max-w-sm">
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-2xl shadow-black/20">
        <div className="grid h-full grid-cols-4 grid-rows-2 gap-2">
          {TILE_FILLS.map((fill, index) => (
            <div
              key={fill}
              className={`rounded-lg bg-gradient-to-br ${fill} ${
                index === TARGET_INDEX ? 'tile-highlight' : 'tile-dim'
              }`}
            />
          ))}
        </div>

        {/* Sweeping viewfinder reticle */}
        <div className="reticle pointer-events-none absolute h-14 w-14 -translate-x-1/2 -translate-y-1/2">
          <span className="absolute left-0 top-0 h-4 w-4 rounded-tl-md border-l-2 border-t-2 border-gold" />
          <span className="absolute right-0 top-0 h-4 w-4 rounded-tr-md border-r-2 border-t-2 border-gold" />
          <span className="absolute bottom-0 left-0 h-4 w-4 rounded-bl-md border-b-2 border-l-2 border-gold" />
          <span className="absolute bottom-0 right-0 h-4 w-4 rounded-br-md border-b-2 border-r-2 border-gold" />
          <span className="lock-ring absolute inset-1 rounded-full border-2 border-focus" />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between rounded-lg border border-line bg-surface px-4 py-3 font-mono text-xs">
        <div className="relative h-4 flex-1 overflow-hidden">
          {CAPTIONS.map((caption, index) => (
            <span
              key={caption}
              className="absolute inset-0 text-ink transition-opacity duration-300"
              style={{ opacity: index === captionIndex ? 1 : 0 }}
            >
              {caption}
            </span>
          ))}
        </div>
        <span className="ml-3 shrink-0 rounded-full bg-focus/15 px-2 py-0.5 text-focus">LIVE DEMO</span>
      </div>
    </div>
  );
}
