import { ArrowRight } from 'lucide-react';
import { FormEvent, useRef, useState } from 'react';

interface Props {
  onSubmit: (code: string) => void;
  loading?: boolean;
}

/**
 * Event codes are exactly six characters, so the input is six cells - the
 * structure of the field teaches the format before the placeholder does.
 * One real <input> underneath keeps typing, paste, and screen readers intact.
 */
export default function EventCodeInput({ onSubmit, loading = false }: Props) {
  const [code, setCode] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const cleanCode = code.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6);
  const valid = cleanCode.length === 6;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (valid) onSubmit(cleanCode);
  }

  const activeCell = Math.min(cleanCode.length, 5);

  return (
    <form className="w-full max-w-md space-y-3" onSubmit={handleSubmit}>
      <div
        className="relative cursor-text"
        onClick={() => inputRef.current?.focus()}
      >
        <input
          ref={inputRef}
          aria-label="Six character event code"
          autoCapitalize="characters"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          className="absolute inset-0 z-10 h-full w-full cursor-text opacity-0"
          value={cleanCode}
          maxLength={6}
          onChange={(event) => setCode(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
        <div aria-hidden className="grid grid-cols-6 gap-1.5">
          {Array.from({ length: 6 }).map((_, i) => {
            const char = cleanCode[i] ?? '';
            const isActive = focused && i === activeCell && !valid;
            return (
              <div
                key={i}
                className={`flex h-12 items-center justify-center rounded-md border bg-surface font-mono text-xl font-semibold text-ink transition-colors sm:h-14 ${
                  isActive ? 'border-gold' : char ? 'border-ink/30' : 'border-line'
                }`}
              >
                {char || (isActive ? <span className="h-6 w-px animate-pulse bg-gold" /> : '')}
              </div>
            );
          })}
        </div>
      </div>
      <button
        className="focus-ring inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-gold font-semibold text-[#1d1622] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        disabled={!valid || loading}
        type="submit"
      >
        {loading ? 'Joining…' : 'Find my photos'}
        <ArrowRight size={18} />
      </button>
    </form>
  );
}
