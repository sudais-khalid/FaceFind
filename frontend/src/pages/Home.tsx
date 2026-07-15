import {
  Camera,
  FolderOpen,
  Moon,
  ScanFace,
  ShieldCheck,
  Sun,
  Sparkles,
  Lock,
  ImageOff,
  Timer,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import EventCodeInput from '../components/EventCodeInput';
import Reveal from '../components/Reveal';
import ScanDemo from '../components/ScanDemo';
import { useStore } from '../store/useStore';
import type { EventSummary } from '../types';

function useScrolled(threshold = 8) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > threshold);
    }
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  return scrolled;
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const stored = window.localStorage.getItem('facefind-theme');
    if (stored === 'light' || stored === 'dark') return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    window.localStorage.setItem('facefind-theme', theme);
  }, [theme]);

  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) };
}

const STEPS = [
  {
    title: 'Scan your face',
    body: "Look at your camera for three seconds. That's it — no account, no photo upload, no waiting in line at a printer.",
    icon: ScanFace,
  },
  {
    title: 'We check every photo',
    body: 'Your face embedding is compared against the entire event album in under a second, using the same matching math as professional recognition systems.',
    icon: Sparkles,
  },
  {
    title: 'Get only your photos',
    body: 'A private gallery of exactly the shots you appear in — nothing else, and nobody else sees which photos matched you.',
    icon: ImageOff,
  },
];

const TRUST_POINTS = [
  {
    title: 'Encrypted, not just stored',
    body: 'Your face embedding is AES-256 encrypted with a key derived per event — it cannot be reused to identify you anywhere else.',
    icon: Lock,
  },
  {
    title: 'Links expire on purpose',
    body: 'Every photo link is single-file and time-limited. Forward one by accident and it stops working on its own within minutes.',
    icon: Timer,
  },
  {
    title: 'No public gallery, ever',
    body: 'There is no page where strangers can browse the album. You only ever see the photos that matched your own scan.',
    icon: ShieldCheck,
  },
];

export default function Home() {
  const navigate = useNavigate();
  const setEvent = useStore((state) => state.setEvent);
  const setUser = useStore((state) => state.setUser);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [organizerLoading, setOrganizerLoading] = useState(false);
  const [organizerError, setOrganizerError] = useState<string | null>(null);
  const { theme, toggle } = useTheme();
  const scrolled = useScrolled();

  async function join(code: string) {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<EventSummary>(`/api/events/join/${code}`);
      const auth = await api.post<{ user: { name: string; email: string; scope: 'attendee'; consentGiven: boolean } }>(
        '/auth/dev-login?role=attendee',
      );
      setEvent(response.data);
      setUser(auth.data.user);
      navigate('/scan');
    } catch {
      setError('Event code was not found.');
    } finally {
      setLoading(false);
    }
  }

  async function organizerLogin() {
    setOrganizerLoading(true);
    setOrganizerError(null);
    try {
      const auth = await api.post<{ user: { name: string; email: string; scope: 'organizer'; consentGiven: boolean } }>(
        '/auth/dev-login?role=organizer',
      );
      setUser(auth.data.user);
      navigate('/dashboard');
    } catch {
      setOrganizerError('Could not sign in. Is the backend running?');
    } finally {
      setOrganizerLoading(false);
    }
  }

  return (
    <main className="app-shell font-sans">
      {/* Nav */}
      <header className={`site-nav ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2 font-display text-lg font-semibold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold text-[#1d1622]">
              <ScanFace size={18} />
            </span>
            FaceFind
          </div>
          <div className="flex items-center gap-4">
            <a className="hidden text-sm text-muted transition hover:text-ink sm:block" href="#how-it-works">
              How it works
            </a>
            <a className="hidden text-sm text-muted transition hover:text-ink sm:block" href="#privacy">
              Privacy
            </a>
            <button
              aria-label="Toggle theme"
              className="focus-ring flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition hover:text-ink active:scale-90"
              onClick={toggle}
              type="button"
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl gap-12 px-5 py-16 sm:py-24 lg:grid-cols-2 lg:items-center">
        <div>
          <span className="hero-in mb-5 inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Face-matched photo retrieval
          </span>
          <h1
            className="hero-in font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-[3.4rem]"
            style={{ animationDelay: '80ms' }}
          >
            Somewhere in this album is a photo of <span className="text-gold">you.</span>
          </h1>
          <p
            className="hero-in mt-6 max-w-lg text-lg leading-relaxed text-muted"
            style={{ animationDelay: '160ms' }}
          >
            Skip the group album. Scan your face once and FaceFind finds every photo and clip you're actually in —
            out of hundreds or thousands, in under a second.
          </p>
          <div className="hero-in mt-8 flex flex-wrap gap-3" style={{ animationDelay: '240ms' }}>
            <a
              className="focus-ring group inline-flex items-center gap-2 rounded-md bg-gold px-5 py-3 font-semibold text-[#1d1622] transition duration-150 hover:brightness-110 active:scale-[0.97]"
              href="#get-started"
            >
              <Camera className="transition-transform duration-200 group-hover:-rotate-6" size={18} />
              Find my photos
            </a>
            <a
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-5 py-3 font-semibold text-ink transition duration-150 hover:bg-surface active:scale-[0.97]"
              href="#how-it-works"
            >
              See how it works
            </a>
          </div>
          <p
            className="hero-in mt-6 flex items-center gap-2 text-sm text-muted"
            style={{ animationDelay: '320ms' }}
          >
            <ShieldCheck className="shrink-0 text-focus" size={16} />
            Your scan is encrypted, single-use for this event, and never shown to other attendees.
          </p>
        </div>

        <div className="hero-in" style={{ animationDelay: '120ms' }}>
          <ScanDemo />
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-line" id="how-it-works">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">How it works</p>
            <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Three steps. No searching.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <Reveal delayMs={index * 100} key={step.title}>
                <div className="group flex h-full flex-col gap-4 rounded-xl border border-line bg-surface p-6 transition duration-300 hover:-translate-y-1 hover:border-gold/40 hover:shadow-lg">
                  <div className="flex items-center justify-between">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-gold/15 text-gold transition-transform duration-300 group-hover:scale-110">
                      <step.icon size={20} />
                    </span>
                    <span className="font-mono text-sm text-muted">0{index + 1}</span>
                  </div>
                  <h3 className="font-display text-xl font-semibold">{step.title}</h3>
                  <p className="text-sm leading-relaxed text-muted">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Privacy / trust */}
      <section className="border-t border-line bg-surface/40" id="privacy">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">Privacy, by construction</p>
            <h2 className="mt-2 max-w-2xl font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Your face is data. We treat it like it matters.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {TRUST_POINTS.map((point, index) => (
              <Reveal delayMs={index * 100} key={point.title}>
                <div className="group flex h-full flex-col gap-3">
                  <point.icon className="text-focus transition-transform duration-300 group-hover:scale-110" size={22} />
                  <h3 className="font-display text-lg font-semibold">{point.title}</h3>
                  <p className="text-sm leading-relaxed text-muted">{point.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Get started */}
      <section className="border-t border-line" id="get-started">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <Reveal>
            <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Get started</h2>
          </Reveal>
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            <Reveal>
              <div className="group h-full rounded-xl border border-line bg-surface p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-gold/40 hover:shadow-lg">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gold text-[#1d1622] shadow-sm shadow-gold/30">
                  <Camera size={22} />
                </div>
                <h3 className="font-display text-xl font-semibold">I have photos to find</h3>
                <p className="mb-5 mt-2 text-sm text-muted">Enter the 6-character event code from your organizer.</p>
                <EventCodeInput loading={loading} onSubmit={join} />
                {error ? <p className="mt-3 text-sm font-medium text-red-500">{error}</p> : null}
              </div>
            </Reveal>
            <Reveal delayMs={100}>
              <div className="group h-full rounded-xl border border-line bg-surface p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-focus/40 hover:shadow-lg">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-focus text-paper shadow-sm shadow-focus/30">
                  <FolderOpen size={22} />
                </div>
                <h3 className="font-display text-xl font-semibold">I'm an organizer</h3>
                <p className="mb-5 mt-2 text-sm text-muted">
                  Create an event from a Google Drive folder and share the event code.
                </p>
                <button
                  className="focus-ring w-full rounded-md bg-ink px-4 py-3 font-semibold text-paper transition duration-150 hover:opacity-90 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100 sm:w-auto"
                  disabled={organizerLoading}
                  onClick={organizerLogin}
                  type="button"
                >
                  {organizerLoading ? 'Signing in…' : 'Continue as organizer'}
                </button>
                {organizerError ? <p className="mt-3 text-sm font-medium text-red-500">{organizerError}</p> : null}
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} FaceFind</span>
          <span>Built for events where the album is bigger than your patience.</span>
        </div>
      </footer>
    </main>
  );
}
