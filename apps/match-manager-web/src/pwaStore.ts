import { create } from 'zustand';

type PwaStore = {
  offlineReady: boolean;
  needRefresh: boolean;
  updateDismissed: boolean;
  error: string | null;
};

export const usePwaStore = create<PwaStore>(() => ({
  offlineReady: false,
  needRefresh: false,
  updateDismissed: false,
  error: null,
}));
