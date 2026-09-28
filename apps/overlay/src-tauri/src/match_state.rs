use std::collections::BTreeSet;
use std::error::Error;
use std::fmt::{self, Display, Formatter};

use serde::{Deserialize, Serialize};

pub const INITIAL_LIFE: u16 = 20;
pub const MAX_LIFE: u16 = 999;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PlayerId {
    PlayerOne,
    PlayerTwo,
}

impl PlayerId {
    #[must_use]
    pub const fn opponent(self) -> Self {
        match self {
            Self::PlayerOne => Self::PlayerTwo,
            Self::PlayerTwo => Self::PlayerOne,
        }
    }

    const fn index(self) -> usize {
        match self {
            Self::PlayerOne => 0,
            Self::PlayerTwo => 1,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BattleStatus {
    PlayerOneAdvantage,
    #[default]
    Even,
    PlayerTwoAdvantage,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TurnAction {
    LevelUp,
    Switch,
    Charge,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayerState {
    pub id: PlayerId,
    pub name: String,
    pub life: u16,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TurnState {
    pub number: u32,
    pub active_player: PlayerId,
    pub used_actions: BTreeSet<TurnAction>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MatchState {
    pub revision: u64,
    pub players: [PlayerState; 2],
    pub battle_status: BattleStatus,
    pub turn: TurnState,
}

impl Default for MatchState {
    fn default() -> Self {
        Self {
            revision: 0,
            players: [
                PlayerState {
                    id: PlayerId::PlayerOne,
                    name: "PLAYER 1".to_owned(),
                    life: INITIAL_LIFE,
                },
                PlayerState {
                    id: PlayerId::PlayerTwo,
                    name: "PLAYER 2".to_owned(),
                    life: INITIAL_LIFE,
                },
            ],
            battle_status: BattleStatus::Even,
            turn: TurnState {
                number: 1,
                active_player: PlayerId::PlayerOne,
                used_actions: BTreeSet::new(),
            },
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum MatchCommand {
    AdjustLife { player: PlayerId, amount: i16 },
    SetLife { player: PlayerId, life: u16 },
    ResetLife { player: PlayerId },
    SetBattleStatus { status: BattleStatus },
    ToggleTurnAction { action: TurnAction },
    ResetTurnActions,
    EndTurn,
    ResetMatch,
    Undo,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MatchStateError {
    LifeOutOfRange { life: u16 },
    TurnNumberOverflow,
    UndoRequiresHistory,
}

impl Display for MatchStateError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::LifeOutOfRange { life } => {
                write!(
                    formatter,
                    "life must be between 0 and {MAX_LIFE}, received {life}"
                )
            }
            Self::TurnNumberOverflow => formatter.write_str("turn number reached its maximum"),
            Self::UndoRequiresHistory => {
                formatter.write_str("undo must be applied by a persistent match store")
            }
        }
    }
}

impl Error for MatchStateError {}

impl MatchState {
    /// Applies one command and returns whether the public state changed.
    ///
    /// # Errors
    ///
    /// Returns an error when an explicit life value exceeds the supported range,
    /// or when advancing the turn would overflow its number.
    pub fn apply(&mut self, command: MatchCommand) -> Result<bool, MatchStateError> {
        let changed = match command {
            MatchCommand::AdjustLife { player, amount } => {
                let life = &mut self.players[player.index()].life;
                let adjusted = i32::from(*life) + i32::from(amount);
                let next_life =
                    u16::try_from(adjusted.clamp(0, i32::from(MAX_LIFE))).unwrap_or(MAX_LIFE);
                replace_if_changed(life, next_life)
            }
            MatchCommand::SetLife { player, life } => {
                if life > MAX_LIFE {
                    return Err(MatchStateError::LifeOutOfRange { life });
                }
                replace_if_changed(&mut self.players[player.index()].life, life)
            }
            MatchCommand::ResetLife { player } => {
                replace_if_changed(&mut self.players[player.index()].life, INITIAL_LIFE)
            }
            MatchCommand::SetBattleStatus { status } => {
                replace_if_changed(&mut self.battle_status, status)
            }
            MatchCommand::ToggleTurnAction { action } => {
                if !self.turn.used_actions.remove(&action) {
                    self.turn.used_actions.insert(action);
                }
                true
            }
            MatchCommand::ResetTurnActions => {
                if self.turn.used_actions.is_empty() {
                    false
                } else {
                    self.turn.used_actions.clear();
                    true
                }
            }
            MatchCommand::EndTurn => {
                self.turn.number = self
                    .turn
                    .number
                    .checked_add(1)
                    .ok_or(MatchStateError::TurnNumberOverflow)?;
                self.turn.active_player = self.turn.active_player.opponent();
                self.turn.used_actions.clear();
                true
            }
            MatchCommand::ResetMatch => {
                let revision = self.revision;
                let initial = Self::default();
                let changed = self.players != initial.players
                    || self.battle_status != initial.battle_status
                    || self.turn != initial.turn;
                *self = initial;
                self.revision = revision;
                changed
            }
            MatchCommand::Undo => return Err(MatchStateError::UndoRequiresHistory),
        };

        if changed {
            self.revision = self.revision.saturating_add(1);
        }

        Ok(changed)
    }
}

fn replace_if_changed<T: Eq>(target: &mut T, value: T) -> bool {
    if *target == value {
        false
    } else {
        *target = value;
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initializes_a_two_player_match() {
        let state = MatchState::default();

        assert_eq!(state.players[0].life, INITIAL_LIFE);
        assert_eq!(state.players[1].life, INITIAL_LIFE);
        assert_eq!(state.battle_status, BattleStatus::Even);
        assert_eq!(state.turn.number, 1);
        assert_eq!(state.turn.active_player, PlayerId::PlayerOne);
        assert!(state.turn.used_actions.is_empty());
        assert_eq!(state.revision, 0);
    }

    #[test]
    fn adjusts_life_without_leaving_the_supported_range() {
        let mut state = MatchState::default();

        state
            .apply(MatchCommand::AdjustLife {
                player: PlayerId::PlayerOne,
                amount: -30,
            })
            .unwrap();
        assert_eq!(state.players[0].life, 0);

        state
            .apply(MatchCommand::AdjustLife {
                player: PlayerId::PlayerTwo,
                amount: i16::MAX,
            })
            .unwrap();
        assert_eq!(state.players[1].life, MAX_LIFE);
        assert_eq!(state.revision, 2);
    }

    #[test]
    fn rejects_an_explicit_life_above_the_maximum() {
        let mut state = MatchState::default();

        let result = state.apply(MatchCommand::SetLife {
            player: PlayerId::PlayerOne,
            life: MAX_LIFE + 1,
        });

        assert_eq!(
            result,
            Err(MatchStateError::LifeOutOfRange { life: MAX_LIFE + 1 })
        );
        assert_eq!(state, MatchState::default());
    }

    #[test]
    fn advances_the_turn_and_clears_once_per_turn_actions() {
        let mut state = MatchState::default();
        state
            .apply(MatchCommand::ToggleTurnAction {
                action: TurnAction::LevelUp,
            })
            .unwrap();
        state
            .apply(MatchCommand::ToggleTurnAction {
                action: TurnAction::Charge,
            })
            .unwrap();

        state.apply(MatchCommand::EndTurn).unwrap();

        assert_eq!(state.turn.number, 2);
        assert_eq!(state.turn.active_player, PlayerId::PlayerTwo);
        assert!(state.turn.used_actions.is_empty());
        assert_eq!(state.revision, 3);
    }

    #[test]
    fn leaves_the_revision_unchanged_for_a_no_op() {
        let mut state = MatchState::default();

        let changed = state
            .apply(MatchCommand::SetBattleStatus {
                status: BattleStatus::Even,
            })
            .unwrap();

        assert!(!changed);
        assert_eq!(state.revision, 0);
    }

    #[test]
    fn serializes_the_api_contract_in_camel_and_snake_case() {
        let state = MatchState::default();
        let json = serde_json::to_value(state).unwrap();

        assert_eq!(json["battleStatus"], "even");
        assert_eq!(json["players"][0]["id"], "player_one");
        assert_eq!(json["turn"]["activePlayer"], "player_one");
        assert_eq!(json["turn"]["usedActions"], serde_json::json!([]));

        let command = MatchCommand::AdjustLife {
            player: PlayerId::PlayerTwo,
            amount: -1,
        };
        assert_eq!(
            serde_json::to_value(command).unwrap(),
            serde_json::json!({
                "type": "adjust_life",
                "player": "player_two",
                "amount": -1
            })
        );
    }
}
