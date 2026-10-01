import { create } from 'zustand';
import {
  createMatchSession,
  type MatchCommand,
  type MatchState,
  type MatchSession,
} from './matchSession';

type Store = {
  match: MatchState | null;
  canUndo: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  dispatch: (command: MatchCommand) => void;
};

let session: MatchSession | undefined;
let initializing: Promise<void> | undefined;
const describeError = (error: unknown) => (error instanceof Error ? error.message : String(error));

export const useMatchStore = create<Store>((set) => ({
  match: null,
  canUndo: false,
  error: null,
  initialize: () => {
    if (session) return Promise.resolve();
    initializing ??= createMatchSession()
      .then((created) => {
        session = created;
        set({ match: created.state, error: null });
      })
      .catch((error: unknown) => {
        set({ error: `起動できませんでした: ${describeError(error)}` });
      })
      .finally(() => {
        initializing = undefined;
      });
    return initializing;
  },
  dispatch: (command) => {
    if (!session) return;
    try {
      const result = session.dispatch(command);
      set({ match: result.state, canUndo: session.canUndo, error: null });
    } catch (error: unknown) {
      set({ error: `操作できませんでした: ${describeError(error)}` });
    }
  },
}));
