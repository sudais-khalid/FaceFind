import { create } from 'zustand';
import type { EventSummary, MatchedFile, User } from '../types';

interface AppState {
  user: User | null;
  event: EventSummary | null;
  probeId: string | null;
  results: MatchedFile[];
  setUser: (user: User | null) => void;
  setEvent: (event: EventSummary | null) => void;
  setProbeId: (probeId: string | null) => void;
  setResults: (results: MatchedFile[]) => void;
  clearAll: () => void;
}

export const useStore = create<AppState>((set) => ({
  user: null,
  event: null,
  probeId: null,
  results: [],
  setUser: (user) => set({ user }),
  setEvent: (event) => set({ event }),
  setProbeId: (probeId) => set({ probeId }),
  setResults: (results) => set({ results }),
  clearAll: () => set({ user: null, event: null, probeId: null, results: [] }),
}));
