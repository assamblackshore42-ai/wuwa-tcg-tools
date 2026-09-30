use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::path::Path;

use rusqlite::{Connection, OptionalExtension, params};

use crate::match_state::{MatchCommand, MatchState, MatchStateError};

const SCHEMA_VERSION: i64 = 2;
const MAX_RETAINED_MATCHES: i64 = 50;

pub struct SqliteMatchStore {
    connection: Connection,
    state: MatchState,
}

#[derive(Debug)]
pub enum MatchStoreError {
    Database(rusqlite::Error),
    Serialization(serde_json::Error),
    State(MatchStateError),
}

impl Display for MatchStoreError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Database(error) => write!(formatter, "database error: {error}"),
            Self::Serialization(error) => write!(formatter, "state serialization error: {error}"),
            Self::State(error) => write!(formatter, "invalid match command: {error}"),
        }
    }
}

impl Error for MatchStoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Database(error) => Some(error),
            Self::Serialization(error) => Some(error),
            Self::State(error) => Some(error),
        }
    }
}

impl From<rusqlite::Error> for MatchStoreError {
    fn from(error: rusqlite::Error) -> Self {
        Self::Database(error)
    }
}

impl From<serde_json::Error> for MatchStoreError {
    fn from(error: serde_json::Error) -> Self {
        Self::Serialization(error)
    }
}

impl From<MatchStateError> for MatchStoreError {
    fn from(error: MatchStateError) -> Self {
        Self::State(error)
    }
}

impl SqliteMatchStore {
    /// Opens a file-backed store and restores its latest match state.
    ///
    /// # Errors
    ///
    /// Returns an error if the database cannot be opened or migrated, or if its
    /// saved state cannot be decoded.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, MatchStoreError> {
        let connection = Connection::open(path)?;
        Self::from_connection(connection)
    }

    /// Opens an isolated in-memory store.
    ///
    /// # Errors
    ///
    /// Returns an error if the schema cannot be initialized.
    pub fn open_in_memory() -> Result<Self, MatchStoreError> {
        let connection = Connection::open_in_memory()?;
        Self::from_connection(connection)
    }

    fn from_connection(mut connection: Connection) -> Result<Self, MatchStoreError> {
        connection.execute_batch("PRAGMA foreign_keys = ON;")?;
        let transaction = connection.transaction()?;
        transaction.execute_batch(
            "CREATE TABLE IF NOT EXISTS match_state (
                 id INTEGER PRIMARY KEY CHECK (id = 1),
                 state_json TEXT NOT NULL,
                 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
             );
             CREATE TABLE IF NOT EXISTS command_history (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 command_json TEXT NOT NULL,
                 state_json TEXT NOT NULL,
                 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
             );
             CREATE TABLE IF NOT EXISTS history_baseline (
                 id INTEGER PRIMARY KEY CHECK (id = 1),
                 state_json TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS command_history_match_resets
                 ON command_history (id)
                 WHERE json_extract(command_json, '$.type') = 'reset_match';",
        )?;
        transaction.execute(
            "INSERT OR IGNORE INTO history_baseline (id, state_json) VALUES (1, ?1)",
            [serde_json::to_string(&MatchState::default())?],
        )?;
        Self::prune_history(&transaction)?;
        transaction.pragma_update(None, "user_version", SCHEMA_VERSION)?;
        transaction.commit()?;

        let saved_json = connection
            .query_row(
                "SELECT state_json FROM match_state WHERE id = 1",
                [],
                |row| row.get::<_, String>(0),
            )
            .optional()?;

        let state = if let Some(json) = saved_json {
            serde_json::from_str(&json)?
        } else {
            let initial = MatchState::default();
            let json = serde_json::to_string(&initial)?;
            connection.execute(
                "INSERT INTO match_state (id, state_json) VALUES (1, ?1)",
                [json],
            )?;
            initial
        };

        Ok(Self { connection, state })
    }

    // A reset starts a new match. Keep the initial state of the oldest retained
    // match as the undo baseline, without retaining any state from older matches.
    fn prune_history(connection: &Connection) -> Result<(), MatchStoreError> {
        let cutoff = connection
            .query_row(
                "SELECT id, state_json FROM command_history
                 WHERE json_extract(command_json, '$.type') = 'reset_match'
                 ORDER BY id DESC LIMIT 1 OFFSET ?1",
                [MAX_RETAINED_MATCHES - 1],
                |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)),
            )
            .optional()?;
        if let Some((id, state_json)) = cutoff {
            connection.execute(
                "UPDATE history_baseline SET state_json = ?1 WHERE id = 1",
                [state_json],
            )?;
            connection.execute("DELETE FROM command_history WHERE id <= ?1", [id])?;
        }
        Ok(())
    }

    #[must_use]
    pub const fn state(&self) -> &MatchState {
        &self.state
    }

    /// Applies and persists a command, returning whether it changed the state.
    ///
    /// The in-memory state is replaced only after the SQLite transaction commits.
    ///
    /// # Errors
    ///
    /// Returns an error if the command is invalid or the resulting command/state
    /// pair cannot be serialized and committed.
    pub fn apply(&mut self, command: MatchCommand) -> Result<bool, MatchStoreError> {
        if command == MatchCommand::Undo {
            return self.undo();
        }

        let mut next_state = self.state.clone();
        let changed = next_state.apply(command)?;

        if !changed {
            return Ok(false);
        }

        let command_json = serde_json::to_string(&command)?;
        let state_json = serde_json::to_string(&next_state)?;
        let transaction = self.connection.transaction()?;
        transaction.execute(
            "UPDATE match_state
             SET state_json = ?1,
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE id = 1",
            [&state_json],
        )?;
        transaction.execute(
            "INSERT INTO command_history (command_json, state_json) VALUES (?1, ?2)",
            params![command_json, state_json],
        )?;
        if command == MatchCommand::ResetMatch {
            Self::prune_history(&transaction)?;
        }
        transaction.commit()?;

        self.state = next_state;
        Ok(true)
    }

    fn undo(&mut self) -> Result<bool, MatchStoreError> {
        let transaction = self.connection.transaction()?;
        let latest_id = transaction
            .query_row(
                "SELECT id FROM command_history ORDER BY id DESC LIMIT 1",
                [],
                |row| row.get::<_, i64>(0),
            )
            .optional()?;
        let Some(latest_id) = latest_id else {
            return Ok(false);
        };

        let previous_json = transaction
            .query_row(
                "SELECT state_json FROM command_history
                 WHERE id < ?1 ORDER BY id DESC LIMIT 1",
                [latest_id],
                |row| row.get::<_, String>(0),
            )
            .optional()?;
        let previous_json = match previous_json {
            Some(json) => json,
            None => transaction.query_row(
                "SELECT state_json FROM history_baseline WHERE id = 1",
                [],
                |row| row.get::<_, String>(0),
            )?,
        };
        let mut previous_state: MatchState = serde_json::from_str(&previous_json)?;
        previous_state.revision = self.state.revision.saturating_add(1);
        let state_json = serde_json::to_string(&previous_state)?;

        transaction.execute("DELETE FROM command_history WHERE id = ?1", [latest_id])?;
        transaction.execute(
            "UPDATE match_state
             SET state_json = ?1,
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE id = 1",
            [state_json],
        )?;
        transaction.commit()?;

        self.state = previous_state;
        Ok(true)
    }

    /// Returns the number of persisted state-changing commands.
    ///
    /// # Errors
    ///
    /// Returns an error if the history table cannot be queried.
    pub fn history_len(&self) -> Result<i64, MatchStoreError> {
        let count =
            self.connection
                .query_row("SELECT COUNT(*) FROM command_history", [], |row| row.get(0))?;
        Ok(count)
    }
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    use crate::match_state::{BattleStatus, INITIAL_LIFE, PlayerId, TurnAction};

    use super::*;

    #[test]
    fn initializes_a_new_store_with_the_default_match() {
        let store = SqliteMatchStore::open_in_memory().unwrap();

        assert_eq!(store.state(), &MatchState::default());
        assert_eq!(store.history_len().unwrap(), 0);
    }

    #[test]
    fn persists_state_changes_and_command_history_together() {
        let mut store = SqliteMatchStore::open_in_memory().unwrap();

        store
            .apply(MatchCommand::AdjustLife {
                player: PlayerId::PlayerOne,
                amount: -3,
            })
            .unwrap();
        store
            .apply(MatchCommand::SetBattleStatus {
                status: BattleStatus::PlayerTwoAdvantage,
            })
            .unwrap();
        store
            .apply(MatchCommand::ToggleTurnAction {
                action: TurnAction::Charge,
            })
            .unwrap();

        assert_eq!(store.state().players[0].life, 17);
        assert_eq!(
            store.state().battle_status,
            BattleStatus::PlayerTwoAdvantage
        );
        assert!(
            store
                .state()
                .turn
                .used_actions
                .contains(&TurnAction::Charge)
        );
        assert_eq!(store.state().revision, 3);
        assert_eq!(store.history_len().unwrap(), 3);
    }

    #[test]
    fn does_not_record_a_command_that_changes_nothing() {
        let mut store = SqliteMatchStore::open_in_memory().unwrap();

        let changed = store
            .apply(MatchCommand::SetBattleStatus {
                status: BattleStatus::Even,
            })
            .unwrap();

        assert!(!changed);
        assert_eq!(store.history_len().unwrap(), 0);
    }

    #[test]
    fn retains_fifty_matches_instead_of_fifty_commands() {
        let mut store = SqliteMatchStore::open_in_memory().unwrap();
        for match_number in 1..=50 {
            for _ in 0..3 {
                store.apply(MatchCommand::EndTurn).unwrap();
            }
            if match_number < 50 {
                store.apply(MatchCommand::ResetMatch).unwrap();
            }
        }
        assert_eq!(store.history_len().unwrap(), 199);

        store.apply(MatchCommand::ResetMatch).unwrap();
        assert_eq!(store.history_len().unwrap(), 196);
        let first_id: i64 = store
            .connection
            .query_row("SELECT MIN(id) FROM command_history", [], |row| row.get(0))
            .unwrap();
        assert_eq!(first_id, 5);
        assert_eq!(store.state().turn.number, 1);

        // No-op resets do not create additional matches or prune more history.
        assert!(!store.apply(MatchCommand::ResetMatch).unwrap());
        assert_eq!(store.history_len().unwrap(), 196);
    }

    #[test]
    fn undo_stops_at_the_oldest_retained_match_after_reopening() {
        let mut store = SqliteMatchStore::open_in_memory().unwrap();
        for _ in 0..55 {
            store.apply(MatchCommand::EndTurn).unwrap();
            store.apply(MatchCommand::ResetMatch).unwrap();
        }
        store.apply(MatchCommand::EndTurn).unwrap();
        let mut restored = SqliteMatchStore::from_connection(store.connection).unwrap();
        assert_eq!(restored.state().turn.number, 2);
        assert_eq!(restored.history_len().unwrap(), 99);

        let revision = restored.state().revision;
        for _ in 0..99 {
            assert!(restored.apply(MatchCommand::Undo).unwrap());
        }
        assert_eq!(restored.state().turn.number, 1);
        assert_eq!(restored.state().revision, revision + 99);
        assert!(!restored.apply(MatchCommand::Undo).unwrap());

        restored.apply(MatchCommand::EndTurn).unwrap();
        restored.apply(MatchCommand::ResetMatch).unwrap();
        assert!(restored.apply(MatchCommand::Undo).unwrap());
        assert_eq!(restored.state().turn.number, 2);
    }

    #[test]
    fn prunes_existing_version_one_history_on_open() {
        let store = SqliteMatchStore::open_in_memory().unwrap();
        store
            .connection
            .execute_batch(
                "DROP TABLE history_baseline;
                 DROP INDEX command_history_match_resets;
                 PRAGMA user_version = 1;",
            )
            .unwrap();
        let mut state = MatchState::default();
        for _ in 0..55 {
            for command in [MatchCommand::EndTurn, MatchCommand::ResetMatch] {
                state.apply(command).unwrap();
                store
                    .connection
                    .execute(
                        "INSERT INTO command_history (command_json, state_json) VALUES (?1, ?2)",
                        params![
                            serde_json::to_string(&command).unwrap(),
                            serde_json::to_string(&state).unwrap()
                        ],
                    )
                    .unwrap();
            }
        }
        store
            .connection
            .execute(
                "UPDATE match_state SET state_json = ?1 WHERE id = 1",
                [serde_json::to_string(&state).unwrap()],
            )
            .unwrap();

        let restored = SqliteMatchStore::from_connection(store.connection).unwrap();
        assert_eq!(restored.state(), &state);
        assert_eq!(restored.history_len().unwrap(), 98);
        let version: i64 = restored
            .connection
            .pragma_query_value(None, "user_version", |row| row.get(0))
            .unwrap();
        assert_eq!(version, SCHEMA_VERSION);
    }

    #[test]
    fn restores_the_latest_state_from_a_file() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "wuwatcg-overlay-store-{}-{unique}.sqlite3",
            std::process::id()
        ));

        {
            let mut store = SqliteMatchStore::open(&path).unwrap();
            store.apply(MatchCommand::EndTurn).unwrap();
        }

        let restored = SqliteMatchStore::open(&path).unwrap();
        assert_eq!(restored.state().turn.number, 2);
        assert_eq!(restored.state().turn.active_player, PlayerId::PlayerTwo);
        assert_eq!(restored.history_len().unwrap(), 1);

        drop(restored);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn undoes_commands_in_reverse_order_with_monotonic_revisions() {
        let mut store = SqliteMatchStore::open_in_memory().unwrap();
        store
            .apply(MatchCommand::AdjustLife {
                player: PlayerId::PlayerOne,
                amount: -1,
            })
            .unwrap();
        store
            .apply(MatchCommand::SetBattleStatus {
                status: BattleStatus::PlayerOneAdvantage,
            })
            .unwrap();

        assert!(store.apply(MatchCommand::Undo).unwrap());
        assert_eq!(store.state().players[0].life, 19);
        assert_eq!(store.state().battle_status, BattleStatus::Even);
        assert_eq!(store.state().revision, 3);
        assert_eq!(store.history_len().unwrap(), 1);

        assert!(store.apply(MatchCommand::Undo).unwrap());
        assert_eq!(store.state().players[0].life, INITIAL_LIFE);
        assert_eq!(store.state().revision, 4);
        assert_eq!(store.history_len().unwrap(), 0);

        assert!(!store.apply(MatchCommand::Undo).unwrap());
        assert_eq!(store.state().revision, 4);
    }
}
