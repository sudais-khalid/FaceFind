import { Download, ImageOff, Loader2, Play, RotateCw, X } from 'lucide-react';
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
    <article className="group overflow-hidden rounded-lg border border-line bg-surface transition duration-300 hover:-translate-y-0.5 hover:border-gold/40 hover:shadow-lg">
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
          className="focus-ring shrink-0 rounded-md p-1.5 text-muted transition duration-150 hover:bg-paper hover:text-ink active:scale-90"
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
  const [urlFailed, setUrlFailed] = useState(false);
  const [mediaLoaded, setMediaLoaded] = useState(false);
  const [mediaFailed, setMediaFailed] = useState(false);
  const [retryToken, setRetryToken] = useState(0);

  function closeLightbox() {
    setActiveUrl(null);
    setActiveFile(null);
  }

  useEffect(() => {
    if (!activeFile) return undefined;
    let cancelled = false;
    setLoadingUrl(true);
    setUrlFailed(false);
    setMediaLoaded(false);
    setMediaFailed(false);
    api
      .get<{ url: string }>(`/api/files/${activeFile.file_id}/url`)
      .then((response) => {
        if (!cancelled) setActiveUrl(response.data.url);
      })
      .catch(() => {
        if (!cancelled) {
          setActiveUrl(null);
          setUrlFailed(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingUrl(false);
      });
    return () => {
      cancelled = true;
    };
    // retryToken deliberately re-runs this effect without changing activeFile
  }, [activeFile, retryToken]);

  useEffect(() => {
    function handleOpenLightbox(e: CustomEvent<MatchedFile>) {
      setActiveFile(e.detail);
      setLoadingUrl(true);
    }

    window.addEventListener('open-lightbox', handleOpenLightbox as EventListener);
    return () => window.removeEventListener('open-lightbox', handleOpenLightbox as EventListener);
  }, []);

  useEffect(() => {
    if (!activeFile) return undefined;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeLightbox();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeFile]);

  const showSpinner = loadingUrl || (Boolean(activeUrl) && !mediaLoaded && !mediaFailed);
  const showError = urlFailed || mediaFailed;

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
          className="overlay-in fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
          onClick={closeLightbox}
        >
          <div
            className="dialog-in max-h-full w-full max-w-5xl overflow-hidden rounded-xl border border-line bg-surface"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <p className="min-w-0 truncate font-mono text-sm text-ink">{activeFile.filename || 'Matched media'}</p>
              <button
                aria-label="Close"
                className="focus-ring rounded-md p-2 text-muted transition hover:text-ink active:scale-90"
                onClick={closeLightbox}
                type="button"
              >
                <X size={20} />
              </button>
            </div>
            <div className="relative flex min-h-[40vh] items-center justify-center bg-black p-2">
              {activeFile.thumbnail_url ? (
                <img
                  alt=""
                  aria-hidden
                  className={`absolute inset-0 h-full w-full scale-105 object-cover object-center opacity-40 blur-xl transition-opacity duration-300 ${
                    mediaLoaded ? 'opacity-0' : 'opacity-40'
                  }`}
                  src={activeFile.thumbnail_url}
                />
              ) : null}

              {showError ? (
                <div className="relative z-10 flex h-[50vh] flex-col items-center justify-center gap-3 px-6 text-center text-white">
                  <ImageOff className="text-white/60" size={32} />
                  <p className="text-sm text-white/80">
                    This preview could not load. It may still be available for download.
                  </p>
                  <button
                    className="focus-ring inline-flex items-center gap-2 rounded-md border border-white/30 px-4 py-2 text-sm font-semibold text-white transition duration-150 hover:bg-white/10 active:scale-[0.97]"
                    onClick={() => setRetryToken((t) => t + 1)}
                    type="button"
                  >
                    <RotateCw size={15} />
                    Try again
                  </button>
                </div>
              ) : activeFile.mime_type?.startsWith('video/') ? (
                <video
                  className={`relative z-10 max-h-[75vh] w-full transition-opacity duration-300 ${mediaLoaded ? 'opacity-100' : 'opacity-0'}`}
                  controls
                  onCanPlay={() => setMediaLoaded(true)}
                  onError={() => setMediaFailed(true)}
                  poster={activeFile.thumbnail_url}
                  preload="metadata"
                  src={activeUrl ?? undefined}
                />
              ) : (
                <img
                  alt=""
                  className={`relative z-10 mx-auto max-h-[75vh] object-contain transition-opacity duration-300 ${mediaLoaded ? 'opacity-100' : 'opacity-0'}`}
                  onError={() => setMediaFailed(true)}
                  onLoad={() => setMediaLoaded(true)}
                  src={activeUrl ?? undefined}
                />
              )}

              {showSpinner && !showError ? (
                <div className="absolute inset-0 z-20 flex items-center justify-center">
                  <Loader2 className="h-10 w-10 animate-spin text-white" size={40} />
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
