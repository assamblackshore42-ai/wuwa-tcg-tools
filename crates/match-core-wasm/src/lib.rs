//! Stateless JSON bindings. Browser storage and history reads belong to adapters.

use match_core::{MatchCommand, MatchState, history_cutoff, restore_undo};
use serde::Serialize;
use wasm_bindgen::prelude::*;

const MAX_SAFE_REVISION: u64 = 9_007_199_254_740_991;

#[derive(Serialize)]
struct CommandResponse {
    changed: bool,
    state: MatchState,
}

fn read_state(json: &str) -> Result<MatchState, String> {
    let state: MatchState = serde_json::from_str(json).map_err(|error| error.to_string())?;
    state.validate().map_err(|error| error.to_string())?;
    validate_revision(&state)?;
    Ok(state)
}

fn validate_revision(state: &MatchState) -> Result<(), String> {
    if state.revision > MAX_SAFE_REVISION {
        return Err("revision exceeds JavaScript's safe integer range".to_owned());
    }
    Ok(())
}

/// Returns the initial match using the Desktop JSON contract.
///
/// # Errors
/// Returns an error if serialization fails.
#[wasm_bindgen]
pub fn initial_state() -> Result<String, String> {
    serde_json::to_string(&MatchState::default()).map_err(|error| error.to_string())
}

/// Validates and canonicalizes a persisted state without applying a command.
///
/// # Errors
/// Returns an error for malformed state or an unsafe revision.
#[wasm_bindgen]
pub fn validate_state(state_json: &str) -> Result<String, String> {
    serde_json::to_string(&read_state(state_json)?).map_err(|error| error.to_string())
}

/// Validates and canonicalizes a command without changing match state.
///
/// # Errors
/// Returns an error for malformed command JSON.
#[wasm_bindgen]
pub fn validate_command(command_json: &str) -> Result<String, String> {
    let command: MatchCommand =
        serde_json::from_str(command_json).map_err(|error| error.to_string())?;
    serde_json::to_string(&command).map_err(|error| error.to_string())
}

/// Computes a candidate state without mutating the adapter's current state.
///
/// # Errors
/// Returns an error for invalid JSON, state, command or an unsafe revision.
/// Undo requires the adapter to provide history through `undo_state` instead.
#[wasm_bindgen]
pub fn apply_command(state_json: &str, command_json: &str) -> Result<String, String> {
    let mut state = read_state(state_json)?;
    let command: MatchCommand =
        serde_json::from_str(command_json).map_err(|error| error.to_string())?;
    let changed = state.apply(command).map_err(|error| error.to_string())?;
    validate_revision(&state)?;
    serde_json::to_string(&CommandResponse { changed, state }).map_err(|error| error.to_string())
}

/// Computes the restored state from a previous entry or history baseline.
///
/// # Errors
/// Returns an error for invalid snapshots or an unsafe revision.
#[wasm_bindgen]
pub fn undo_state(current_json: &str, previous_json: &str) -> Result<String, String> {
    let current = read_state(current_json)?;
    let previous = read_state(previous_json)?;
    let state = restore_undo(&current, previous).map_err(|error| error.to_string())?;
    validate_revision(&state)?;
    serde_json::to_string(&state).map_err(|error| error.to_string())
}

/// Selects the prune boundary from newest-first reset entry indices.
///
/// # Errors
/// Returns an error if indices are not a JSON array of unsigned 32-bit integers.
#[wasm_bindgen]
pub fn history_cutoff_index(reset_indices_json: &str) -> Result<Option<u32>, String> {
    let indices: Vec<u32> =
        serde_json::from_str(reset_indices_json).map_err(|error| error.to_string())?;
    Ok(history_cutoff(indices))
}

/// Returns the shared retention limit, including the ongoing match.
#[wasm_bindgen]
#[must_use]
pub fn retained_match_limit() -> usize {
    match_core::MAX_RETAINED_MATCHES
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};

    use super::*;

    #[test]
    fn rejects_invalid_json_commands_and_state() {
        assert!(apply_command("{}", r#"{"type":"end_turn"}"#).is_err());
        let initial = initial_state().unwrap();
        for command in [
            "{",
            r#"{"type":"unknown"}"#,
            r#"{"type":"undo"}"#,
            r#"{"type":"set_life","player":"player_one","life":1000}"#,
        ] {
            assert!(apply_command(&initial, command).is_err());
        }
        let mut invalid: Value = serde_json::from_str(&initial).unwrap();
        invalid["turn"]["number"] = json!(0);
        assert!(apply_command(&invalid.to_string(), r#"{"type":"end_turn"}"#).is_err());
    }

    #[test]
    fn protects_the_javascript_integer_boundary() {
        let mut state = MatchState {
            revision: MAX_SAFE_REVISION,
            ..MatchState::default()
        };
        let json = serde_json::to_string(&state).unwrap();
        assert!(apply_command(&json, r#"{"type":"reset_match"}"#).is_ok());
        assert!(apply_command(&json, r#"{"type":"end_turn"}"#).is_err());
        assert!(undo_state(&json, &initial_state().unwrap()).is_err());
        state.revision += 1;
        assert!(
            apply_command(
                &serde_json::to_string(&state).unwrap(),
                r#"{"type":"reset_match"}"#
            )
            .is_err()
        );
    }
}
