import { Camera } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import FrameCorners from './FrameCorners';

interface Props {
  onFramesCaptured: (frames: Blob[]) => void;
  disabled?: boolean;
}

const FRAME_COUNT = 7;

export default function FaceScanCamera({ onFramesCaptured, disabled = false }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [capturing, setCapturing] = useState(false);
  const [warmingUp, setWarmingUp] = useState(true);
  const warmupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then((stream) => {
        if (!active) return;
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        // Give the camera 2 seconds to settle exposure and white balance
        warmupTimerRef.current = window.setTimeout(() => {
          setWarmingUp(false);
        }, 2000);
      })
      .catch(() => setError('Camera access is blocked. Allow camera access in your browser and reload this page.'));

    return () => {
      active = false;
      if (warmupTimerRef.current) window.clearTimeout(warmupTimerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function captureFrames() {
    if (!videoRef.current || disabled || warmingUp) return;
    setCapturing(true);
    setProgress(0);
    const frames: Blob[] = [];
    const captureCanvas = document.createElement('canvas');
    captureCanvas.width = 640;
    captureCanvas.height = 480;
    const context = captureCanvas.getContext('2d');
    if (!context) return;

    for (let index = 0; index < FRAME_COUNT; index += 1) {
      context.drawImage(videoRef.current, 0, 0, captureCanvas.width, captureCanvas.height);
      const blob = await new Promise<Blob | null>((resolve) =>
        captureCanvas.toBlob(resolve, 'image/jpeg', 0.85),
      );
      if (blob) frames.push(blob);
      setProgress(index + 1);
      if (index < FRAME_COUNT - 1) await new Promise((resolve) => window.setTimeout(resolve, 800));
    }

    setCapturing(false);
    onFramesCaptured(frames);
  }

  const statusText = warmingUp
    ? 'ADJUSTING EXPOSURE'
    : capturing
    ? `FRAME ${Math.max(progress, 1)}/${FRAME_COUNT}`
    : 'READY';

  return (
    <section className="space-y-4">
      <div className="relative overflow-hidden rounded-xl bg-black">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="aspect-[4/3] w-full scale-x-[-1] object-cover"
        />
        <FrameCorners
          colorClass={capturing ? 'border-focus' : 'border-gold'}
          sizeClass="h-7 w-7"
          insetClass="inset-[12%]"
        />

        {/* camera status line, styled like an on-sensor readout */}
        <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent px-4 pb-3 pt-8 font-mono text-xs tracking-[0.12em] text-white">
          <span className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                capturing ? 'rec-dot bg-red-500' : warmingUp ? 'bg-white/40' : 'bg-focus'
              }`}
            />
            {statusText}
          </span>
          <span className="text-white/60">640×480</span>
        </div>
      </div>

      {error ? (
        <p className="rounded-md border border-red-300/40 bg-red-500/10 px-4 py-3 text-sm text-red-600">{error}</p>
      ) : null}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* one cell per captured frame - the progress bar IS the film strip */}
        <div aria-label={`${progress} of ${FRAME_COUNT} frames captured`} className="flex items-center gap-1.5" role="img">
          {Array.from({ length: FRAME_COUNT }).map((_, i) => (
            <span
              key={i}
              className={`h-6 w-8 rounded-[3px] border transition-colors duration-300 ${
                i < progress ? 'border-gold bg-gold/80' : 'border-line bg-surface'
              }`}
            />
          ))}
        </div>
        <button
          className="focus-ring inline-flex items-center justify-center gap-2 rounded-md bg-gold px-5 py-2.5 font-semibold text-[#1d1622] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          disabled={capturing || disabled || Boolean(error) || warmingUp}
          onClick={captureFrames}
          type="button"
        >
          <Camera size={18} />
          {capturing ? 'Hold still…' : warmingUp ? 'Adjusting camera…' : 'Start scan'}
        </button>
      </div>

      <p className="text-sm text-muted">
        Look at the camera and blink naturally. The scan takes about five seconds and captures {FRAME_COUNT} frames.
      </p>
    </section>
  );
}
