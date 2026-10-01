import Dexie, { type Table } from 'dexie';
import type { MatchCommand, MatchState } from './matchSession';

export const MATCH_DATABASE_NAME = 'wuwa-tcg-match-manager';
export const DATA_FORMAT_VERSION = 1;
export const DATABASE_SCHEMA_VERSION = 1;

export type MatchRecord = {
  id: 'current';
  formatVersion: number;
  state: MatchState;
  baseline: MatchState;
};

export type HistoryEntry = {
  id?: number;
  command: MatchCommand;
  state: MatchState;
  isReset: 0 | 1;
};

export class MatchDatabase extends Dexie {
  records!: Table<MatchRecord, string>;
  history!: Table<HistoryEntry, number>;

  constructor(name = MATCH_DATABASE_NAME) {
    super(name);
    this.version(DATABASE_SCHEMA_VERSION).stores({ records: 'id', history: '++id,isReset' });
  }
}
