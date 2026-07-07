import { Camera, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface Props {
  onFramesCaptured: (frames: Blob[]) => void;
  disabled?: boolean;
}

const challenges = ['Look straight ahead', 'Blink your eyes', 'Slowly nod your head'];

export default function FaceScanCamera({ onFramesCaptured, disabled = false }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [capturing, setCapturing] = useState(false);
  const [warmingUp, setWarmingUp] = useState(true);
  const [challengeIndex, setChallengeIndex] = useState(0);
  const warmupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then((stream) => {
        if (!active) return;
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        // Start 2-second warm-up after camera stream is ready
        warmupTimerRef.current = window.setTimeout(() => {
          setWarmingUp(false);
        }, 2000);
      })
      .catch(() => setError('Camera access is unavailable.'));

    return () => {
      active = false;
      if (warmupTimerRef.current) window.clearTimeout(warmupTimerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setChallengeIndex((current) => (current + 1) % challenges.length);
    }, 1500);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let frame = 0;
    let animation = 0;
    const draw = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas) {
        const context = canvas.getContext('2d');
        if (context) {
          canvas.width = video.clientWidth || 640;
          canvas.height = video.clientHeight || 480;
          context.clearRect(0, 0, canvas.width, canvas.height);
          context.strokeStyle = '#0E9F6E';
          context.lineWidth = 3;
          const width = canvas.width * 0.42;
          const height = canvas.height * 0.58;
          context.strokeRect((canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
          context.fillStyle = '#0E9F6E';
          context.fillRect(16, 16, Math.min(canvas.width - 32, (progress / 7) * (canvas.width - 32)), 6);
        }
      }
      frame += 1;
      animation = window.requestAnimationFrame(draw);
    };
    draw();
    return () => {
      window.cancelAnimationFrame(animation);
      void frame;
    };
  }, [progress]);

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

    for (let index = 0; index < 7; index += 1) {
      context.drawImage(videoRef.current, 0, 0, captureCanvas.width, captureCanvas.height);
      const blob = await new Promise<Blob | null>((resolve) =>
        captureCanvas.toBlob(resolve, 'image/jpeg', 0.85),
      );
      if (blob) frames.push(blob);
      setProgress(index + 1);
      if (index < 6) await new Promise((resolve) => window.setTimeout(resolve, 800));
    }

    setCapturing(false);
    onFramesCaptured(frames);
  }

  return (
    <section className="space-y-4">
      <div className="relative overflow-hidden rounded-lg bg-slate-950">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="aspect-[4/3] w-full object-cover"
        />
        <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />
        <div className="absolute left-4 top-8 rounded-md bg-white/95 px-3 py-2 text-sm font-semibold text-slate-900">
          {warmingUp ? 'Adjusting camera...' : challenges[challengeIndex]}
        </div>
      </div>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          {warmingUp
            ? 'Warming up camera...'
            : progress === 0
            ? 'Ready'
            : `${progress} of 7 frames`}
        </p>
        <button
          className="focus-ring inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-semibold text-white disabled:bg-slate-400"
          disabled={capturing || disabled || Boolean(error) || warmingUp}
          onClick={captureFrames}
          type="button"
        >
          {capturing ? <RotateCcw className="animate-spin" size={18} /> : <Camera size={18} />}
          {capturing ? 'Capturing' : warmingUp ? 'Warming up...' : 'Start Scan'}
        </button>
      </div>
    </section>
  );
}
