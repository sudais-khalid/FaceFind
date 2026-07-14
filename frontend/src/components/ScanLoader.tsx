import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import FrameCorners from './FrameCorners';
import { useStore } from '../store/useStore';
import type { MatchedFile } from '../types';

const loaderMessages = [
  'Reading your scan…',
  'Checking every photo in the album…',
  'Collecting your matches…',
  'Almost there…',
];

// Decorative stand-ins for album photos while the search runs - same visual
// language as the landing page demo, now doing the real thing.
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

interface Props {
  probeId: string;
  eventCode: string;
}

export default function ScanLoader({ probeId }: Props) {
  const navigate = useNavigate();
  const setResults = useStore((state) => state.setResults);
  const [messageIndex, setMessageIndex] = useState(0);
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);
  const [results, setResultsState] = useState<MatchedFile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % loaderMessages.length);
    }, 1500);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setMinTimeElapsed(true), 3000);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function fetchResults() {
      try {
        const response = await api.get<{ high_confidence: MatchedFile[]; medium_confidence: MatchedFile[]; total: number }>(
          `/api/search/results/${probeId}`,
        );
        if (!cancelled) {
          const tagged = [
            ...response.data.high_confidence.map((file) => ({ ...file, confidence: 'high' as const })),
            ...response.data.medium_confidence.map((file) => ({ ...file, confidence: 'medium' as const })),
          ];
          setResultsState(tagged);
        }
      } catch {
        if (!cancelled) {
          setError('Your results could not be loaded.');
        }
      }
    }
    fetchResults();
    return () => {
      cancelled = true;
    };
  }, [probeId]);

  useEffect(() => {
    if (minTimeElapsed && results !== null && !error) {
      setResults(results);
      navigate('/results');
    }
  }, [minTimeElapsed, results, error, navigate, setResults]);

  return (
    <main className="app-shell flex items-center justify-center font-sans">
      <div className="w-full max-w-sm px-5">
        <div className="relative overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-xl">
          <div className="grid aspect-[4/3] grid-cols-4 grid-rows-2 gap-2">
            {TILE_FILLS.map((fill, index) => (
              <div
                key={fill}
                className={`rounded-lg bg-gradient-to-br ${fill} ${index === 4 ? 'tile-highlight' : 'tile-dim'}`}
              />
            ))}
          </div>
          <div className="reticle pointer-events-none absolute h-14 w-14 -translate-x-1/2 -translate-y-1/2">
            <FrameCorners colorClass="border-gold" sizeClass="h-4 w-4" insetClass="inset-0" />
            <span className="lock-ring absolute inset-1 rounded-full border-2 border-focus" />
          </div>
        </div>

        <div className="mt-4 flex min-h-[3.5rem] items-center justify-between rounded-lg border border-line bg-surface px-4 py-3 font-mono text-xs text-ink">
          {error ? (
            <span className="text-red-500">{error}</span>
          ) : (
            <span aria-live="polite">{loaderMessages[messageIndex]}</span>
          )}
          {!error && <span className="ml-3 shrink-0 rounded-full bg-focus/15 px-2 py-0.5 text-focus">SEARCHING</span>}
        </div>

        {error ? (
          <div className="mt-4 flex gap-3">
            <button
              className="focus-ring flex-1 rounded-md bg-gold px-4 py-2.5 font-semibold text-[#1d1622] transition hover:brightness-110"
              onClick={() => window.location.reload()}
              type="button"
            >
              Try again
            </button>
            <button
              className="focus-ring flex-1 rounded-md border border-line px-4 py-2.5 font-semibold text-ink transition hover:bg-paper"
              onClick={() => navigate('/scan')}
              type="button"
            >
              Back to scan
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}
