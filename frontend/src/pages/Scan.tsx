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
            : 'This event is still indexing. Please wait until the organizer dashboard shows it is ready.',
        );
      } else if (errorResponse.response?.status === 400) {
        setError("We couldn't verify your face. Please try again in good lighting.");
      } else {
        setError(errorResponse.response?.data?.detail ?? 'Scan could not be completed. Please try again.');
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
    <main className="app-shell">
      <div className="mx-auto max-w-4xl px-5 py-8">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase text-primary">{event?.title ?? 'Event scan'}</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-950">Face scan</h1>
        </header>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <FaceScanCamera disabled={!consented || submitting} onFramesCaptured={submitFrames} />
          {submitting ? <p className="mt-4 text-sm text-slate-600">Processing scan...</p> : null}
          {error ? <p className="mt-4 text-sm font-medium text-red-700">{error}</p> : null}
        </div>
      </div>
      {!consented ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
          <section className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-md bg-accent text-white">
              <ShieldCheck size={22} />
            </div>
            <h2 className="text-xl font-semibold text-slate-950">Consent required</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              FaceFind captures short webcam frames to extract a face embedding for this event. Raw scan images are not stored.
              Embeddings are encrypted, scoped to this event, and can be deleted with your account data.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button className="focus-ring rounded-md border border-slate-300 px-4 py-2 font-semibold transition hover:bg-slate-50" onClick={() => navigate('/')} type="button">
                Cancel
              </button>
              <button className="focus-ring rounded-md bg-primary px-4 py-2 font-semibold text-white transition hover:bg-primary/90" onClick={agree} type="button">
                I Agree & Continue
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
