import { Download, Play, X, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import FrameCorners from './FrameCorners';
import type { MatchedFile } from '../types';

interface Props {
  highConfidenceFiles: MatchedFile[];
  mediumConfidenceFiles: MatchedFile[];
}

function matchTag(confidence?: string) {
  if (confidence === 'high') {
    return (
      <span className="rounded-sm bg-gold px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-[0.1em] text-[#1d1622]">
        MATCH
      </span>
    );
  }
  if (confidence === 'medium') {
    return (
      <span className="rounded-sm border border-white/50 bg-black/40 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.1em] text-white">
        LIKELY
      </span>
    );
  }
  return null;
}

function FileCard({ file }: { file: MatchedFile }) {
  const imgRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [thumbLoaded, setThumbLoaded] = useState(false);
  const [thumbError, setThumbError] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.disconnect();
          }
        });
      },
      { rootMargin: '100px', threshold: 0.1 },
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }
    return () => observer.disconnect();
  }, []);

  const isVideo = file.mime_type?.startsWith('video/');

  return (
    <article className="group overflow-hidden rounded-lg border border-line bg-surface transition-shadow hover:shadow-lg">
      <button
        className="relative block aspect-[4/3] w-full overflow-hidden bg-ink/5"
        onClick={() => window.dispatchEvent(new CustomEvent('open-lightbox', { detail: file }))}
        type="button"
        aria-label={isVideo ? `Play ${file.filename || 'video'}` : `View ${file.filename || 'photo'}`}
      >
        <div ref={imgRef} className="h-full w-full" />
        {isVisible && file.thumbnail_url && !thumbError ? (
          <img
            alt=""
            className={`absolute inset-0 h-full w-full object-cover transition duration-300 group-hover:scale-[1.03] ${
              thumbLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            src={file.thumbnail_url}
            onLoad={() => setThumbLoaded(true)}
            onError={() => setThumbError(true)}
          />
        ) : isVisible && thumbError ? (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-muted">Preview unavailable</div>
        ) : (
          <div className="absolute inset-0 animate-pulse bg-line/60" />
        )}

        {/* focus-lock on hover: the app's signature moment, per photo */}
        <FrameCorners
          colorClass="border-gold"
          sizeClass="h-4 w-4"
          insetClass="inset-2"
          className="opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        />

        {isVideo ? (
          <span className="absolute inset-0 flex items-center justify-center bg-black/25 text-white">
            <Play size={34} />
          </span>
        ) : null}
        <div className="absolute right-2 top-2">{matchTag(file.confidence)}</div>
      </button>
      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <p className="min-w-0 truncate font-mono text-xs text-muted">{file.filename || file.file_id.slice(0, 12)}</p>
        <button
          aria-label={`Download ${file.filename || 'file'}`}
          className="focus-ring shrink-0 rounded-md p-1.5 text-muted transition hover:bg-paper hover:text-ink"
          onClick={async () => {
            try {
              const response = await api.get<{ url: string }>(`/api/files/${file.file_id}/url`);
              // download=1 returns Content-Disposition: attachment with the
              // original filename and extension.
              const anchor = document.createElement('a');
              anchor.href = `${response.data.url}&download=1`;
              document.body.appendChild(anchor);
              anchor.click();
              anchor.remove();
            } catch {
              // fallback handled by browser
            }
          }}
          type="button"
        >
          <Download size={16} />
        </button>
      </div>
    </article>
  );
}

export default function ResultsGallery({ highConfidenceFiles, mediumConfidenceFiles }: Props) {
  const [activeUrl, setActiveUrl] = useState<string | null>(null);
  const [activeFile, setActiveFile] = useState<MatchedFile | null>(null);
  const [loadingUrl, setLoadingUrl] = useState(false);

  useEffect(() => {
    function handleOpenLightbox(e: CustomEvent<MatchedFile>) {
      setActiveFile(e.detail);
      setLoadingUrl(true);
      api
        .get<{ url: string }>(`/api/files/${e.detail.file_id}/url`)
        .then((response) => setActiveUrl(response.data.url))
        .catch(() => setActiveUrl(''))
        .finally(() => setLoadingUrl(false));
    }

    window.addEventListener('open-lightbox', handleOpenLightbox as EventListener);
    return () => window.removeEventListener('open-lightbox', handleOpenLightbox as EventListener);
  }, []);

  useEffect(() => {
    if (!activeFile) return undefined;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setActiveUrl(null);
        setActiveFile(null);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeFile]);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {highConfidenceFiles.map((file) => (
          <FileCard key={file.file_id} file={file} />
        ))}
      </div>

      {mediumConfidenceFiles.length > 0 ? (
        <>
          <div className="mt-10 border-t border-line pt-6">
            <h2 className="font-display text-lg font-semibold text-ink">More possible matches</h2>
            <p className="mt-1 text-sm text-muted">
              These look similar to you but scored lower. Worth a quick look before downloading.
            </p>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {mediumConfidenceFiles.map((file) => (
              <FileCard key={file.file_id} file={file} />
            ))}
          </div>
        </>
      ) : null}

      {activeFile ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
          onClick={() => {
            setActiveUrl(null);
            setActiveFile(null);
          }}
        >
          <div
            className="max-h-full w-full max-w-5xl overflow-hidden rounded-xl border border-line bg-surface"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <p className="min-w-0 truncate font-mono text-sm text-ink">{activeFile.filename || 'Matched media'}</p>
              <button
                aria-label="Close"
                className="focus-ring rounded-md p-2 text-muted transition hover:text-ink"
                onClick={() => {
                  setActiveUrl(null);
                  setActiveFile(null);
                }}
                type="button"
              >
                <X size={20} />
              </button>
            </div>
            <div className="bg-black p-2">
              {loadingUrl ? (
                <div className="flex h-[60vh] items-center justify-center text-white">
                  <Loader2 className="h-10 w-10 animate-spin" size={40} />
                </div>
              ) : activeFile.mime_type?.startsWith('video/') ? (
                <video className="max-h-[75vh] w-full" controls src={activeUrl ?? undefined} preload="metadata" />
              ) : (
                <img alt="" className="mx-auto max-h-[75vh] object-contain" src={activeUrl ?? undefined} />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
