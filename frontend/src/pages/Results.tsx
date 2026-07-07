import { Download, RotateCcw, Image, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import ResultsGallery from '../components/ResultsGallery';
import { useStore } from '../store/useStore';
import type { MatchedFile } from '../types';

export default function Results() {
  const navigate = useNavigate();
  const event = useStore((state) => state.event);
  const results = useStore((state) => state.results);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(false);
  }, []);

  const highConfidenceFiles = results.filter((f) => f.confidence === 'high');
  const mediumConfidenceFiles = results.filter((f) => f.confidence === 'medium');

  async function downloadAll() {
    setDownloading(true);
    setDownloadError(null);
    try {
      const zip = new (await import('jszip')).default();
      await Promise.all(
        highConfidenceFiles.map(async (file, index) => {
          const urlResponse = await api.get<{ url: string }>(`/api/files/${file.file_id}/url`);
          const blob = await fetch(urlResponse.data.url).then((response) => response.blob());
          zip.file(`facefind-${index + 1}`, blob);
        }),
      );
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'facefind-results.zip';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError('Could not download files. Please try again.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="app-shell">
      <div className="mx-auto max-w-6xl px-5 py-8">
        <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-semibold uppercase text-primary">{event?.title ?? 'Results'}</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">Your matched media</h1>
            <p className="mt-2 text-sm text-slate-600">
              Found {highConfidenceFiles.length} confirmed photo{highConfidenceFiles.length !== 1 ? 's' : ''} and{' '}
              {mediumConfidenceFiles.length} possible match{mediumConfidenceFiles.length !== 1 ? 'es' : ''}.
            </p>
          </div>
          {highConfidenceFiles.length ? (
            <button
              className="focus-ring inline-flex items-center gap-2 rounded-md bg-slate-950 px-4 py-2 font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={downloading}
              onClick={downloadAll}
              type="button"
            >
              <Download size={18} />
              {downloading ? 'Preparing download...' : 'Download All'}
            </button>
          ) : null}
        </header>
        {downloadError ? <p className="mb-6 text-sm text-red-700">{downloadError}</p> : null}
        {error ? (
          <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>
        ) : results.length === 0 ? (
          <section className="rounded-lg border border-slate-200 bg-white p-8 text-center">
            <h2 className="text-xl font-semibold text-slate-950">No photos found for you in this album</h2>
            <button className="focus-ring mt-5 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-semibold text-white" onClick={() => navigate('/scan')} type="button">
              <RotateCcw size={18} />
              Retry scan
            </button>
          </section>
        ) : (
          <ResultsGallery highConfidenceFiles={highConfidenceFiles} mediumConfidenceFiles={mediumConfidenceFiles} />
        )}
      </div>
    </main>
  );
}
