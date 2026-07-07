import { Copy, FolderPlus, QrCode } from 'lucide-react';
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

export default function OrganizerDashboard() {
  const event = useStore((state) => state.event);
  const setEvent = useStore((state) => state.setEvent);
  const [title, setTitle] = useState('');
  const [driveUrl, setDriveUrl] = useState('');
  const [status, setStatus] = useState<EventStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setError('Could not create event. Check the Drive folder URL and try again.');
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

  const total = status?.files_total ?? 0;
  const indexed = status?.files_indexed ?? 0;
  const percent = total > 0 ? Math.round((indexed / total) * 100) : 0;

  return (
    <main className="app-shell">
      <div className="mx-auto max-w-6xl px-5 py-8">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase text-primary">Organizer</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-950">Event dashboard</h1>
        </header>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <form className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" onSubmit={createEvent}>
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-md bg-accent text-white">
              <FolderPlus size={22} />
            </div>
            <label className="block text-sm font-semibold text-slate-700" htmlFor="title">Event title</label>
            <input id="title" className="focus-ring mt-2 h-11 w-full rounded-md border border-slate-300 px-3 transition focus:border-primary" value={title} onChange={(e) => setTitle(e.target.value)} required />
            <label className="mt-4 block text-sm font-semibold text-slate-700" htmlFor="drive">Drive folder URL</label>
            <input id="drive" className="focus-ring mt-2 h-11 w-full rounded-md border border-slate-300 px-3 transition focus:border-primary" value={driveUrl} onChange={(e) => setDriveUrl(e.target.value)} required />
            <button className="focus-ring mt-5 rounded-md bg-primary px-4 py-2 font-semibold text-white transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-slate-400" disabled={loading} type="submit">
              {loading ? 'Creating...' : 'Create event'}
            </button>
            {error ? <p className="mt-3 text-sm font-medium text-red-700">{error}</p> : null}
          </form>
          <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-md bg-slate-950 text-white">
              <QrCode size={22} />
            </div>
            {event ? (
              <div className="space-y-5">
                <div>
                  <p className="text-sm text-slate-600">Event code</p>
                  <p className="mt-1 text-4xl font-bold tracking-wide text-slate-950">{event.event_code}</p>
                </div>
                <QRCodeCanvas value={joinUrl} size={180} />
                <button className="focus-ring inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 font-semibold transition hover:bg-slate-50" onClick={() => navigator.clipboard.writeText(joinUrl)} type="button">
                  <Copy size={18} />
                  Share
                </button>
                <div>
                  <div className="mb-2 flex justify-between text-sm font-medium text-slate-600">
                    <span className="capitalize">{status?.status ?? 'pending'}</span>
                    <span>{percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                    <div className="h-2 rounded-full bg-accent transition-all duration-500" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{indexed} of {total} files indexed</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-600">Create an event to generate a code and QR link.</p>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}
