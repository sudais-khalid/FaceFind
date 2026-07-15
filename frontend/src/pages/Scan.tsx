import { ShieldCheck } from 'lucide-react';
import { AxiosError } from 'axios';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import FaceScanCamera from '../components/FaceScanCamera';
import ScanLoader from '../components/ScanLoader';
import { useStore } from '../store/useStore';

export default function Scan() {
  const navigate = useNavigate();
  const event = useStore((state) => state.event);
  const user = useStore((state) => state.user);
  const setUser = useStore((state) => state.setUser);
  const setProbeId = useStore((state) => state.setProbeId);
  const [consented, setConsented] = useState(Boolean(user?.consentGiven));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showLoader, setShowLoader] = useState(false);
  const [probeId, setLocalProbeId] = useState<string | null>(null);

  async function submitFrames(frames: Blob[]) {
    if (!event) return;
    setSubmitting(true);
    setError(null);
    const form = new FormData();
    frames.forEach((frame, index) => form.append('frames', frame, `frame-${index}.jpg`));
    form.append('event_code', event.event_code);
    try {
      const response = await api.post<{ probe_id: string; search_ready: boolean }>('/api/scan', form);
      setLocalProbeId(response.data.probe_id);
      setProbeId(response.data.probe_id);
      setShowLoader(true);
    } catch (caught) {
      const errorResponse = caught as AxiosError<{ detail?: string }>;
      if (errorResponse.response?.status === 409) {
        setError(
          errorResponse.response?.data?.detail?.toLowerCase().includes('failed')
            ? errorResponse.response.data.detail
            : 'This album is still being indexed. Try again in a few minutes.',
        );
      } else if (errorResponse.response?.status === 400) {
        setError("We couldn't detect your face clearly. Face the camera in even lighting and try again.");
      } else {
        setError(errorResponse.response?.data?.detail ?? 'The scan could not be completed. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  function agree() {
    const nextUser = user ? { ...user, consentGiven: true } : null;
    setUser(nextUser);
    setConsented(true);
  }

  if (showLoader && probeId) {
    return <ScanLoader probeId={probeId} eventCode={event?.event_code || ''} />;
  }

  return (
    <main className="app-shell font-sans">
      <div className="mx-auto max-w-2xl px-5 py-10">
        <header className="mb-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">
            {event?.title ?? 'Event'} · {event?.event_code ?? ''}
          </p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-ink">Scan your face</h1>
          <p className="mt-2 text-muted">One scan finds every photo of you in this album.</p>
        </header>
        <div className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-6">
          <FaceScanCamera disabled={!consented || submitting} onFramesCaptured={submitFrames} />
          {submitting ? <p className="mt-4 font-mono text-sm text-muted">Uploading frames…</p> : null}
          {error ? <p className="mt-4 text-sm font-medium text-red-500">{error}</p> : null}
        </div>
      </div>

      {!consented ? (
        <div className="overlay-in fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <section className="dialog-in w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-2xl">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-focus text-paper">
              <ShieldCheck size={22} />
            </div>
            <h2 className="font-display text-xl font-semibold text-ink">Before you scan</h2>
            <ul className="mt-4 space-y-2.5 text-sm leading-6 text-muted">
              <li>Your camera takes a few frames to recognize your face in this event's photos.</li>
              <li>The frames themselves are never stored - only an encrypted signature of your face.</li>
              <li>That signature works for this event only and expires within a day.</li>
              <li>No other attendee can see your scan or your results.</li>
            </ul>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="focus-ring rounded-md border border-line px-4 py-2 font-semibold text-ink transition duration-150 hover:bg-paper active:scale-[0.97]"
                onClick={() => navigate('/')}
                type="button"
              >
                Cancel
              </button>
              <button
                className="focus-ring rounded-md bg-gold px-4 py-2 font-semibold text-[#1d1622] transition duration-150 hover:brightness-110 active:scale-[0.97]"
                onClick={agree}
                type="button"
              >
                Agree and scan
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
