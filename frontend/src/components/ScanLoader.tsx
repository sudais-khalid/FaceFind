import { RotateCcw, Search, Image, Clock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useStore } from '../store/useStore';
import type { MatchedFile } from '../types';

const loaderMessages = [
  { text: 'Analyzing your face...', icon: Image },
  { text: 'Searching through the album...', icon: Search },
  { text: 'Finding your photos...', icon: Image },
  { text: 'Almost there...', icon: Clock },
];

interface Props {
  probeId: string;
  eventCode: string;
}

export default function ScanLoader({ probeId, eventCode }: Props) {
  const navigate = useNavigate();
  const setResults = useStore((state) => state.setResults);
  const setProbeId = useStore((state) => state.setProbeId);
  const [messageIndex, setMessageIndex] = useState(0);
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);
  const [results, setResultsState] = useState<MatchedFile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Cycle messages every 1.5 seconds
  useEffect(() => {
    const interval = window.setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % loaderMessages.length);
    }, 1500);
    return () => window.clearInterval(interval);
  }, []);

  // Minimum 3 second display
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setMinTimeElapsed(true);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, []);

  // Fetch results after scan completes
  useEffect(() => {
    let cancelled = false;
    async function fetchResults() {
      try {
        const response = await api.get<{ high_confidence: MatchedFile[]; medium_confidence: MatchedFile[]; total: number }>(
          `/api/search/results/${probeId}`
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
          setError('Could not load results. Please try again.');
        }
      }
    }
    fetchResults();
    return () => {
      cancelled = true;
    };
  }, [probeId]);

  // Navigate when both conditions are met
  useEffect(() => {
    if (minTimeElapsed && results !== null) {
      if (error) return; // Show retry button instead
      setResults(results);
      navigate('/results');
    }
  }, [minTimeElapsed, results, error, navigate, setResults]);

  const handleRetry = async () => {
    setError(null);
    setResultsState(null);
    setMinTimeElapsed(false);
    try {
      const response = await api.get<{ high_confidence: MatchedFile[]; medium_confidence: MatchedFile[]; total: number }>(
        `/api/search/results/${probeId}`
      );
      const tagged = [
        ...response.data.high_confidence.map((file) => ({ ...file, confidence: 'high' as const })),
        ...response.data.medium_confidence.map((file) => ({ ...file, confidence: 'medium' as const })),
      ];
      setResultsState(tagged);
    } catch {
      setError('Could not load results. Please try again.');
    }
  };

  const CurrentIcon = loaderMessages[messageIndex].icon;

  return (
    <main className="app-shell">
      <div className="mx-auto max-w-md px-5 py-16">
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mx-auto">
            <RotateCcw className="animate-spin text-primary" size={32} />
          </div>
          <h2 className="text-xl font-semibold text-slate-950">Processing your scan</h2>
          <p className="mt-2 text-sm text-slate-600">
            <CurrentIcon className="inline mr-1" size={16} />
            {loaderMessages[messageIndex].text}
          </p>
          
          {/* Indeterminate progress bar */}
          <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full w-1/4 bg-primary animate-[shimmer_1.5s_infinite]" />
          </div>

          {error ? (
            <div className="mt-6 space-y-3">
              <p className="text-sm text-red-700">{error}</p>
              <button
                className="focus-ring inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-semibold text-white"
                onClick={handleRetry}
                type="button"
              >
                <RotateCcw size={18} />
                Retry
              </button>
              <button
                className="focus-ring inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 font-semibold text-slate-700"
                onClick={() => navigate('/scan')}
                type="button"
              >
                Back to Scan
              </button>
            </div>
          ) : (
            <p className="mt-4 text-xs text-slate-500">
              {minTimeElapsed ? 'Finalizing...' : 'Please wait...'}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
