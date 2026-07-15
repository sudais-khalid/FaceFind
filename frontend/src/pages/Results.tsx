import { Download, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import ResultsGallery from '../components/ResultsGallery';
import { useStore } from '../store/useStore';

export default function Results() {
  const navigate = useNavigate();
  const event = useStore((state) => state.event);
  const results = useStore((state) => state.results);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const highConfidenceFiles = results.filter((f) => f.confidence === 'high');
  const mediumConfidenceFiles = results.filter((f) => f.confidence === 'medium');

  async function downloadAll() {
    setDownloading(true);
    setDownloadError(null);
    try {
      const zip = new (await import('jszip')).default();
      const extFromMime = (mime?: string) => {
        if (!mime) return 'jpg';
        const map: Record<string, string> = {
          'image/jpeg': 'jpg',
          'image/png': 'png',
          'image/webp': 'webp',
          'image/heic': 'heic',
          'video/mp4': 'mp4',
          'video/quicktime': 'mov',
        };
        return map[mime] ?? mime.split('/')[1] ?? 'bin';
      };
      await Promise.all(
        highConfidenceFiles.map(async (file, index) => {
          const urlResponse = await api.get<{ url: string }>(`/api/files/${file.file_id}/url`);
          const blob = await fetch(urlResponse.data.url).then((response) => response.blob());
          const name = file.filename || `facefind-${index + 1}.${extFromMime(file.mime_type)}`;
          zip.file(name, blob);
        }),
      );
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'facefind-photos.zip';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError('The download failed partway. Try again.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="app-shell font-sans">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <header className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">
              {event?.title ?? 'Results'}
              {event?.event_code ? ` · ${event.event_code}` : ''}
            </p>
            <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              Your photos
            </h1>
            <p className="mt-2 text-muted">
              {highConfidenceFiles.length > 0
                ? `${highConfidenceFiles.length} confirmed ${highConfidenceFiles.length === 1 ? 'photo' : 'photos'}` +
                  (mediumConfidenceFiles.length > 0
                    ? ` and ${mediumConfidenceFiles.length} more that might be you.`
                    : '.')
                : mediumConfidenceFiles.length > 0
                ? `${mediumConfidenceFiles.length} possible ${mediumConfidenceFiles.length === 1 ? 'match' : 'matches'} - take a look.`
                : ''}
            </p>
          </div>
          {highConfidenceFiles.length ? (
            <button
              className="focus-ring inline-flex shrink-0 items-center gap-2 rounded-md bg-gold px-5 py-2.5 font-semibold text-[#1d1622] transition duration-150 hover:brightness-110 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
              disabled={downloading}
              onClick={downloadAll}
              type="button"
            >
              <Download size={18} />
              {downloading ? 'Preparing zip…' : 'Download all'}
            </button>
          ) : null}
        </header>
        {downloadError ? <p className="mb-6 text-sm font-medium text-red-500">{downloadError}</p> : null}

        {results.length === 0 ? (
          <section className="relative rounded-xl border border-line bg-surface px-8 py-16 text-center">
            <h2 className="font-display text-xl font-semibold text-ink">No photos of you in this album yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted">
              If you expected matches, try scanning again closer to the camera and in even lighting.
            </p>
            <button
              className="focus-ring mt-6 inline-flex items-center gap-2 rounded-md bg-gold px-5 py-2.5 font-semibold text-[#1d1622] transition duration-150 hover:brightness-110 active:scale-[0.97]"
              onClick={() => navigate('/scan')}
              type="button"
            >
              <RotateCcw size={18} />
              Scan again
            </button>
          </section>
        ) : (
          <ResultsGallery highConfidenceFiles={highConfidenceFiles} mediumConfidenceFiles={mediumConfidenceFiles} />
        )}
      </div>
    </main>
  );
}
