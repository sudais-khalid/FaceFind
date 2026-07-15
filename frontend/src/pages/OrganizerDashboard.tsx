import { Check, Copy, FolderPlus } from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';
import { QRCodeCanvas } from 'qrcode.react';
import { api } from '../api/client';
import { useStore } from '../store/useStore';

interface EventStatus {
  status: string;
  files_total: number;
  files_indexed: number;
  last_indexed_at: string | null;
}

const STATUS_COPY: Record<string, string> = {
  pending: 'Waiting to start…',
  indexing: 'Indexing photos…',
  ready: 'Ready - attendees can scan now',
  error: 'Indexing hit a problem. Re-create the event or try reindexing.',
};

export default function OrganizerDashboard() {
  const event = useStore((state) => state.event);
  const setEvent = useStore((state) => state.setEvent);
  const [title, setTitle] = useState('');
  const [driveUrl, setDriveUrl] = useState('');
  const [status, setStatus] = useState<EventStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const joinUrl = event ? `${window.location.origin}/?event_code=${event.event_code}` : '';

  async function createEvent(formEvent: FormEvent) {
    formEvent.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await api.post<{ event_id: string; event_code: string; status: string }>('/api/events', {
        title,
        drive_folder_url: driveUrl,
      });
      setEvent({ event_id: response.data.event_id, event_code: response.data.event_code, title });
      setStatus({ status: response.data.status, files_total: 0, files_indexed: 0, last_indexed_at: null });
    } catch {
      setError('The event could not be created. Check the Drive folder link and try again.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!event) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const response = await api.get<EventStatus>(`/api/events/${event.event_id}/status`);
        setStatus(response.data);
      } catch {
        // transient poll failure - retried on next tick
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [event]);

  function copyLink() {
    navigator.clipboard.writeText(joinUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  const total = status?.files_total ?? 0;
  const indexed = status?.files_indexed ?? 0;
  const percent = total > 0 ? Math.round((indexed / total) * 100) : 0;
  const statusLine = STATUS_COPY[status?.status ?? 'pending'] ?? status?.status ?? '';

  return (
    <main className="app-shell font-sans">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <header className="mb-8">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">Organizer</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-ink">Your event</h1>
        </header>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <form className="rounded-xl border border-line bg-surface p-6 shadow-sm" onSubmit={createEvent}>
            <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-focus text-paper">
              <FolderPlus size={22} />
            </div>
            <h2 className="font-display text-lg font-semibold text-ink">Create an event from a Drive folder</h2>
            <p className="mt-1 text-sm text-muted">
              Share the folder publicly or with the service account first, then paste its link here.
            </p>

            <label className="mt-5 block text-sm font-semibold text-ink" htmlFor="title">
              Event name
            </label>
            <input
              id="title"
              className="focus-ring mt-2 h-11 w-full rounded-md border border-line bg-paper px-3 text-ink transition focus:border-gold"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Convocation 2026"
              required
            />
            <label className="mt-4 block text-sm font-semibold text-ink" htmlFor="drive">
              Google Drive folder link
            </label>
            <input
              id="drive"
              className="focus-ring mt-2 h-11 w-full rounded-md border border-line bg-paper px-3 font-mono text-sm text-ink transition focus:border-gold"
              value={driveUrl}
              onChange={(e) => setDriveUrl(e.target.value)}
              placeholder="https://drive.google.com/drive/folders/…"
              required
            />
            <button
              className="focus-ring mt-6 rounded-md bg-gold px-5 py-2.5 font-semibold text-[#1d1622] transition duration-150 hover:brightness-110 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
              disabled={loading}
              type="submit"
            >
              {loading ? 'Creating…' : 'Create event'}
            </button>
            {error ? <p className="mt-3 text-sm font-medium text-red-500">{error}</p> : null}
          </form>

          <aside className="rounded-xl border border-line bg-surface p-6 shadow-sm">
            {event ? (
              <div className="space-y-6">
                <div>
                  <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">Event code</p>
                  <div className="mt-2 grid grid-cols-6 gap-1.5" aria-label={`Event code ${event.event_code}`}>
                    {event.event_code.split('').map((char, i) => (
                      <div
                        key={i}
                        className="flex h-12 items-center justify-center rounded-md border border-ink/30 bg-paper font-mono text-xl font-semibold text-ink"
                      >
                        {char}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="shrink-0 rounded-lg border border-line bg-white p-2">
                    <QRCodeCanvas value={joinUrl} size={120} />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <p className="text-sm text-muted">
                      Attendees scan the code or open the link and type the event code.
                    </p>
                    <button
                      className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink transition duration-150 hover:bg-paper active:scale-[0.97]"
                      onClick={copyLink}
                      type="button"
                    >
                      {copied ? <Check className="text-focus" size={16} /> : <Copy size={16} />}
                      {copied ? 'Copied' : 'Copy join link'}
                    </button>
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex items-baseline justify-between">
                    <span className="text-sm font-medium text-ink">{statusLine}</span>
                    <span className="font-mono text-xs text-muted">
                      {indexed} / {total}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-line">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        status?.status === 'error' ? 'bg-red-500' : status?.status === 'ready' ? 'bg-focus' : 'bg-gold'
                      }`}
                      style={{ width: `${status?.status === 'ready' ? 100 : percent}%` }}
                    />
                  </div>
                  {status?.status === 'indexing' ? (
                    <p className="mt-2 text-xs text-muted">
                      Large albums take a few minutes. Attendees can scan as soon as this finishes.
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center py-12 text-center">
                <p className="max-w-[220px] text-sm text-muted">
                  Your event code and QR appear here once the event is created.
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}
