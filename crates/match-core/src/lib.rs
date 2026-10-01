//! Shared match rules. Storage, transport and application runtimes live in adapters.

mod history;
mod state;

pub use history::{MAX_RETAINED_MATCHES, history_cutoff, restore_undo};
pub use state::{
    BattleStatus, INITIAL_LIFE, MAX_LIFE, MatchCommand, MatchState, MatchStateError, PlayerId,
    PlayerState, TurnAction, TurnState,
};
