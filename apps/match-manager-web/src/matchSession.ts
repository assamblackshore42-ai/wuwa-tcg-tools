import { liveQuery } from 'dexie';
import type { MatchCommand, MatchState } from '../../match-manager/src/api/matchApi';
import { loadWasm } from './wasmApi';
import {
  DATA_FORMAT_VERSION,
  DATABASE_SCHEMA_VERSION,
  MatchDatabase,
  type HistoryEntry,
  type MatchRecord,
} from './matchDatabase';

export type { MatchCommand, MatchState };
export type CommandResult = { changed: boolean; state: MatchState };
export type MatchSnapshot = { state: MatchState; canUndo: boolean };
type Engine = Awaited<ReturnType<typeof loadWasm>>;

export class StorageDataError extends Error {
  constructor() {
    super('保存した対戦データを読み込めません。データは変更していません。');
  }
}

// All calculations are synchronous Wasm calls inside IndexedDB transactions.
// Network/Wasm initialization must finish before any transaction starts.
export class MatchSession {
  private current: MatchSnapshot;
  private queue: Promise<void> = Promise.resolve();
  private listeners = new Set<() => void>();

  private constructor(
    private readonly engine: Engine,
    readonly database: MatchDatabase,
  ) {
    this.current = { state: JSON.parse(engine.initial_state()) as MatchState, canUndo: false };
  }

  static async open(name?: string): Promise<MatchSession> {
    const session = new MatchSession(await loadWasm(), new MatchDatabase(name));
    try {
      await session.database.open();
      // Dexie keeps verno at the declared version when opening a newer DB.
      // Its native IndexedDB schema version is the declared version times ten.
      if (session.database.backendDB().version !== DATABASE_SCHEMA_VERSION * 10)
        throw new StorageDataError();
      await session.database.transaction(
        'rw',
        session.database.records,
        session.database.history,
        async () => {
          const record = await session.database.records.get('current');
          const history = await session.database.history.toArray();
          if (!record) {
            if (history.length || (await session.database.records.count()))
              throw new StorageDataError();
            const initial = session.state;
            await session.database.records.add({
              id: 'current',
              formatVersion: DATA_FORMAT_VERSION,
              state: initial,
              baseline: initial,
            });
          } else {
            session.validateRecord(record);
            for (const entry of history) session.validateEntry(entry);
            const reference = history.at(-1)?.state ?? record.baseline;
            if (
              JSON.stringify({ ...record.state, revision: 0 }) !==
              JSON.stringify({ ...reference, revision: 0 })
            )
              throw new StorageDataError();
            await session.prune(record);
          }
        },
      );
      session.accept(await session.snapshot());
      return session;
    } catch (error) {
      session.close();
      throw error;
    }
  }

  get state(): MatchState {
    return structuredClone(this.current.state);
  }
  get canUndo(): boolean {
    return this.current.canUndo;
  }

  private validateRecord(record: MatchRecord): void {
    try {
      if (record.id !== 'current' || record.formatVersion !== DATA_FORMAT_VERSION)
        throw new StorageDataError();
      record.state = JSON.parse(
        this.engine.validate_state(JSON.stringify(record.state)),
      ) as MatchState;
      record.baseline = JSON.parse(
        this.engine.validate_state(JSON.stringify(record.baseline)),
      ) as MatchState;
    } catch {
      throw new StorageDataError();
    }
  }

  private validateEntry(entry: HistoryEntry): void {
    try {
      if (!Number.isSafeInteger(entry.id) || entry.id! <= 0) throw new StorageDataError();
      const command = JSON.parse(
        this.engine.validate_command(JSON.stringify(entry.command)),
      ) as MatchCommand;
      if (command.type === 'undo' || entry.isReset !== (command.type === 'reset_match' ? 1 : 0))
        throw new StorageDataError();
      entry.state = JSON.parse(
        this.engine.validate_state(JSON.stringify(entry.state)),
      ) as MatchState;
    } catch {
      throw new StorageDataError();
    }
  }

  private async readRecord(): Promise<MatchRecord> {
    const record = await this.database.records.get('current');
    if (!record) throw new StorageDataError();
    this.validateRecord(record);
    return record;
  }

  private async prune(record: MatchRecord): Promise<void> {
    const resets = await this.database.history
      .where('isReset')
      .equals(1)
      .reverse()
      .limit(this.engine.retained_match_limit())
      .toArray();
    const index = this.engine.history_cutoff_index(JSON.stringify(resets.map((_, index) => index)));
    if (index === undefined) return;
    const boundary = resets[index]!;
    this.validateEntry(boundary);
    record.baseline = boundary.state;
    await this.database.records.put(record);
    await this.database.history.where(':id').belowOrEqual(boundary.id!).delete();
  }

  async snapshot(): Promise<MatchSnapshot> {
    return this.database.transaction(
      'r',
      this.database.records,
      this.database.history,
      async () => {
        const record = await this.readRecord();
        return { state: record.state, canUndo: (await this.database.history.count()) > 0 };
      },
    );
  }

  private accept(snapshot: MatchSnapshot): boolean {
    if (snapshot.state.revision < this.current.state.revision) return false;
    this.current = structuredClone(snapshot);
    return true;
  }

  subscribe(next: (snapshot: MatchSnapshot) => void, error: (error: unknown) => void): () => void {
    const subscription = liveQuery(() => this.snapshot()).subscribe({
      next: (snapshot) => {
        if (this.accept(snapshot)) next(snapshot);
      },
      error,
    });
    const unsubscribe = () => {
      subscription.unsubscribe();
      this.listeners.delete(unsubscribe);
    };
    this.listeners.add(unsubscribe);
    return unsubscribe;
  }

  dispatch(input: MatchCommand): Promise<CommandResult> {
    const command = structuredClone(input);
    const result = this.queue.then(() => this.apply(command));
    // A failed command must not poison subsequent commands in the queue.
    this.queue = result.then(
      () => {},
      () => {},
    );
    return result;
  }

  private async apply(command: MatchCommand): Promise<CommandResult> {
    const result = await this.database.transaction(
      'rw',
      this.database.records,
      this.database.history,
      async () => {
        const record = await this.readRecord();
        const latest = await this.database.history.orderBy(':id').last();
        let candidate: CommandResult;
        if (command.type === 'undo') {
          if (!latest) return { changed: false, state: record.state, canUndo: false };
          this.validateEntry(latest);
          const previous = await this.database.history.where(':id').below(latest.id!).last();
          if (previous) this.validateEntry(previous);
          const state = JSON.parse(
            this.engine.undo_state(
              JSON.stringify(record.state),
              JSON.stringify(previous?.state ?? record.baseline),
            ),
          ) as MatchState;
          candidate = { changed: true, state };
          await this.database.history.delete(latest.id!);
        } else {
          candidate = JSON.parse(
            this.engine.apply_command(JSON.stringify(record.state), JSON.stringify(command)),
          ) as CommandResult;
          if (!candidate.changed) return { ...candidate, canUndo: Boolean(latest) };
          await this.database.history.add({
            command,
            state: candidate.state,
            isReset: command.type === 'reset_match' ? 1 : 0,
          });
        }
        // Transactions serialize access across tabs: never compute from cached UI state.
        if (candidate.state.revision !== record.state.revision + 1) throw new StorageDataError();
        record.state = candidate.state;
        await this.database.records.put(record);
        if (command.type === 'reset_match') await this.prune(record);
        return { ...candidate, canUndo: (await this.database.history.count()) > 0 };
      },
    );
    // This promise resolves only after the entire IndexedDB transaction commits.
    this.accept({ state: result.state, canUndo: result.canUndo });
    return { changed: result.changed, state: result.state };
  }

  close(): void {
    for (const unsubscribe of this.listeners) unsubscribe();
    this.database.close();
  }
}

export function createMatchSession(name?: string): Promise<MatchSession> {
  return MatchSession.open(name);
}
