import type { MatchCommand, MatchState } from '../../match-manager/src/api/matchApi';
import { loadWasm } from './wasmApi';

export type { MatchCommand, MatchState };
export type CommandResult = { changed: boolean; state: MatchState };
type Engine = Awaited<ReturnType<typeof loadWasm>>;
type Entry = { command: MatchCommand; state: MatchState };

// Temporary memory adapter. IndexedDB transactions are introduced in step 3.
export class MatchSession {
  private current: MatchState;
  private baseline: MatchState;
  private history: Entry[] = [];

  constructor(private readonly engine: Engine) {
    this.current = JSON.parse(engine.initial_state()) as MatchState;
    this.baseline = this.state;
  }

  get state(): MatchState {
    return structuredClone(this.current);
  }

  get canUndo(): boolean {
    return this.history.length > 0;
  }

  dispatch(command: MatchCommand): CommandResult {
    if (command.type === 'undo') {
      if (!this.canUndo) return { changed: false, state: this.state };
      const previous = this.history.at(-2)?.state ?? this.baseline;
      const restored = JSON.parse(
        this.engine.undo_state(JSON.stringify(this.current), JSON.stringify(previous)),
      ) as MatchState;
      this.history.pop();
      this.current = restored;
      return { changed: true, state: this.state };
    }

    const result = JSON.parse(
      this.engine.apply_command(JSON.stringify(this.current), JSON.stringify(command)),
    ) as CommandResult;
    if (!result.changed) return { changed: false, state: this.state };
    let nextHistory = [...this.history, { command: structuredClone(command), state: result.state }];
    let baseline = this.baseline;
    if (command.type === 'reset_match') {
      const resets = nextHistory
        .flatMap((entry, index) => (entry.command.type === 'reset_match' ? [index] : []))
        .reverse();
      const cutoff = this.engine.history_cutoff_index(JSON.stringify(resets));
      if (cutoff !== undefined) {
        baseline = nextHistory[cutoff]!.state;
        nextHistory = nextHistory.slice(cutoff + 1);
      }
    }
    this.history = nextHistory;
    this.baseline = baseline;
    this.current = result.state;
    return { changed: true, state: this.state };
  }
}

export async function createMatchSession(): Promise<MatchSession> {
  return new MatchSession(await loadWasm());
}
