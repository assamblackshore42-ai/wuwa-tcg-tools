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
  pending: number;
  error: string | null;
  initialize: () => Promise<void>;
  dispatch: (command: MatchCommand) => Promise<void>;
};

let session: MatchSession | undefined;
let initializing: Promise<void> | undefined;
let failureGeneration = 0;
const describeError = (error: unknown) => (error instanceof Error ? error.message : String(error));

function saveError(error: unknown): string {
  const name = error instanceof Error ? error.name : '';
  if (name === 'QuotaExceededError')
    return '空き容量が不足して保存できませんでした。保存に失敗した操作は反映していません。';
  return `保存できませんでした。保存に失敗した操作は反映していません。${describeError(error)}`;
}

export const useMatchStore = create<Store>((set) => ({
  match: null,
  canUndo: false,
  pending: 0,
  error: null,
  initialize: () => {
    if (session) return Promise.resolve();
    initializing ??= createMatchSession()
      .then((created) => {
        session = created;
        set({ match: created.state, canUndo: created.canUndo, error: null });
        created.subscribe(
          (snapshot) => {
            set((current) =>
              current.match && current.match.revision > snapshot.state.revision
                ? {}
                : { match: snapshot.state, canUndo: snapshot.canUndo },
            );
          },
          (error) => set({ error: `保存した対戦を読み込めませんでした。${describeError(error)}` }),
        );
        // Best effort only; denial must not prevent normal IndexedDB saving.
        void navigator.storage?.persist?.().catch(() => {});
      })
      .catch((error: unknown) => {
        set({ error: `起動できませんでした: ${describeError(error)}` });
      })
      .finally(() => {
        initializing = undefined;
      });
    return initializing;
  },
  dispatch: async (command) => {
    if (!session) return;
    const generation = failureGeneration;
    set((current) => ({ pending: current.pending + 1 }));
    try {
      const result = await session.dispatch(command);
      set((current) => {
        const error = generation === failureGeneration ? null : current.error;
        return current.match && current.match.revision > result.state.revision
          ? { error }
          : { match: result.state, canUndo: session!.canUndo, error };
      });
    } catch (error: unknown) {
      failureGeneration++;
      set({ error: saveError(error) });
    } finally {
      set((current) => ({ pending: current.pending - 1 }));
    }
  },
}));
