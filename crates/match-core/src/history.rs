use crate::{MatchState, MatchStateError};

/// Includes the ongoing match; only state-changing resets start a new match.
pub const MAX_RETAINED_MATCHES: usize = 50;

/// Selects the reset starting the oldest retained match from newest-first resets.
///
/// The adapter retains that reset's state as the undo baseline and deletes all
/// history through the reset, inclusive. IDs and storage reads belong to adapters.
pub fn history_cutoff<T>(newest_first_resets: impl IntoIterator<Item = T>) -> Option<T> {
    newest_first_resets
        .into_iter()
        .nth(MAX_RETAINED_MATCHES - 1)
}

/// Restores the previous history state, or the baseline when history is exhausted.
///
/// Call only when a latest history entry exists. Its removal and persistence of
/// the returned state must be committed together by the storage adapter.
///
/// # Errors
///
/// Returns an error if the restored state violates the match invariants.
pub fn restore_undo(
    current: &MatchState,
    previous: MatchState,
) -> Result<MatchState, MatchStateError> {
    previous.validate()?;
    let mut restored = previous;
    restored.revision = current.revision.saturating_add(1);
    Ok(restored)
}

#[cfg(test)]
mod tests {
    use crate::MatchCommand;

    use super::*;

    #[test]
    fn cutoff_counts_matches_and_keeps_the_ongoing_match() {
        assert_eq!(history_cutoff(1..=49), None);
        assert_eq!(history_cutoff((1..=50).rev()), Some(1));
        assert_eq!(history_cutoff((1..=55).rev()), Some(6));
    }

    #[test]
    fn undo_restores_content_but_uses_the_current_revision() {
        let previous = MatchState::default();
        let mut current = previous.clone();
        current.apply(MatchCommand::EndTurn).unwrap();
        current.revision = 20;
        let restored = restore_undo(&current, previous).unwrap();
        assert_eq!(restored.turn.number, 1);
        assert_eq!(restored.revision, 21);
        current.revision = u64::MAX;
        assert_eq!(restore_undo(&current, restored).unwrap().revision, u64::MAX);
    }

    #[test]
    fn undo_rejects_an_invalid_history_state() {
        let mut previous = MatchState::default();
        previous.turn.number = 0;
        assert_eq!(
            restore_undo(&MatchState::default(), previous),
            Err(MatchStateError::InvalidTurnNumber)
        );
    }
}
