import { ArrowRight } from 'lucide-react';
import { FormEvent, useState } from 'react';

interface Props {
  onSubmit: (code: string) => void;
  loading?: boolean;
}

export default function EventCodeInput({ onSubmit, loading = false }: Props) {
  const [code, setCode] = useState('');
  const cleanCode = code.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6);
  const valid = cleanCode.length === 6;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (valid) onSubmit(cleanCode);
  }

  return (
    <form className="flex w-full max-w-md gap-2" onSubmit={handleSubmit}>
      <input
        aria-label="Event code"
        className="focus-ring h-12 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-4 text-lg font-semibold uppercase tracking-[0.18em]"
        value={cleanCode}
        onChange={(event) => setCode(event.target.value)}
        placeholder="ABC234"
      />
      <button
        className="focus-ring inline-flex h-12 items-center gap-2 rounded-md bg-primary px-4 font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
        disabled={!valid || loading}
        type="submit"
      >
        <ArrowRight size={18} />
        Join
      </button>
    </form>
  );
}
