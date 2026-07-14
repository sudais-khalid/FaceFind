import { Download, Play, X, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { MatchedFile } from '../types';

interface Props {
  highConfidenceFiles: MatchedFile[];
  mediumConfidenceFiles: MatchedFile[];
}

function confidenceBadge(confidence?: string) {
  if (confidence === 'high') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
        <CheckCircle size={10} />
          High Match
        </span>
      );
    }
  if (confidence === 'medium') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
        <AlertCircle size={10} />
        Possible Match
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
      { rootMargin: '100px', threshold: 0.1 }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }
    return () => observer.disconnect();
  }, []);

  const isVideo = file.mime_type?.startsWith('video/');

  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <button
        className="relative block aspect-[4/3] w-full bg-slate-100"
        onClick={() => window.dispatchEvent(new CustomEvent('open-lightbox', { detail: file }))}
                  type="button"
        aria-label={isVideo ? 'Play video' : 'View photo'}
                >
        <div ref={imgRef} className="h-full w-full" />
        {isVisible && file.thumbnail_url && !thumbError ? (
                <img
                  alt=""
            className={`h-full w-full object-cover transition-opacity duration-300 ${thumbLoaded ? 'opacity-100' : 'opacity-0'}`}
            src={file.thumbnail_url}
            onLoad={() => setThumbLoaded(true)}
            onError={() => setThumbError(true)}
                />
        ) : isVisible && thumbError ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">Preview unavailable</div>
        ) : (
          <div className="h-full w-full animate-pulse bg-slate-200" />
        )}
        {isVideo ? (
          <span className="absolute inset-0 flex items-center justify-center bg-black/20 text-white">
            <Play size={34} />
          </span>
        ) : null}
        {file.confidence && (
          <div className="absolute right-2 top-2 z-10">
            {confidenceBadge(file.confidence)}
        </div>
        )}
      </button>
      <div className="flex items-center justify-between gap-3 p-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">{file.filename || `File ${file.file_id.slice(0, 8)}`}</p>
          {file.confidence && <p className="text-xs text-slate-500 capitalize">{file.confidence} confidence</p>}
        </div>
        <button
          aria-label="Download"
          className="focus-ring rounded-md border border-slate-300 p-2 text-slate-700 hover:bg-slate-50"
          onClick={async () => {
            try {
              const response = await api.get<{ url: string }>(`/api/files/${file.file_id}/url`);
              // download=1 makes the media proxy respond with a Content-Disposition
              // attachment carrying the original filename and extension.
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
          <Download size={18} />
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
      api.get<{ url: string }>(`/api/files/${e.detail.file_id}/url`)
        .then((response) => {
          setActiveUrl(response.data.url);
        })
        .catch(() => {
          setActiveUrl('');
        })
        .finally(() => {
          setLoadingUrl(false);
        });
    }

    window.addEventListener('open-lightbox', handleOpenLightbox as EventListener);
    return () => window.removeEventListener('open-lightbox', handleOpenLightbox as EventListener);
  }, []);

  return (
    <>
      {mediumConfidenceFiles.length > 0 ? (
        <h2 className="mb-4 text-lg font-semibold text-slate-950">Your Photos</h2>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {highConfidenceFiles.map((file) => (
          <FileCard key={file.file_id} file={file} />
        ))}
      </div>
      {mediumConfidenceFiles.length > 0 ? (
        <>
          <div className="my-8 border-t border-slate-200 pt-6">
            <h2 className="text-lg font-semibold text-slate-950">More Possible Matches</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {mediumConfidenceFiles.map((file) => (
              <FileCard key={file.file_id} file={file} />
            ))}
          </div>
        </>
      ) : null}
      {activeFile ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4">
          <div className="max-h-full w-full max-w-5xl overflow-hidden rounded-lg bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 p-3">
              <p className="font-semibold text-slate-900">Matched media</p>
              <button className="focus-ring rounded-md p-2" onClick={() => { setActiveUrl(null); setActiveFile(null); }} type="button">
                <X size={20} />
              </button>
            </div>
            <div className="bg-slate-950 p-2">
              {loadingUrl ? (
                <div className="flex h-[60vh] items-center justify-center text-white">
                  <Loader2 className="animate-spin h-10 w-10" size={40} />
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

