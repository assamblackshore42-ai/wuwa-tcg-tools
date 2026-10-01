//! Generates per-command expectations from the actual Desktop SQLite adapter.
use std::fs;

use serde::Serialize;
use wuwa_tcg_match_manager_lib::match_state::{
    BattleStatus, MatchCommand, MatchState, PlayerId, TurnAction,
};
use wuwa_tcg_match_manager_lib::match_store::SqliteMatchStore;

#[derive(Serialize)]
struct Step {
    command: MatchCommand,
    changed: bool,
    state: MatchState,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).ok_or("provide an output file")?;
    let mut commands = vec![
        MatchCommand::Undo,
        MatchCommand::ResetMatch,
        MatchCommand::AdjustLife {
            player: PlayerId::PlayerOne,
            amount: -3,
        },
        MatchCommand::SetLife {
            player: PlayerId::PlayerTwo,
            life: 999,
        },
        MatchCommand::AdjustLife {
            player: PlayerId::PlayerTwo,
            amount: 1,
        },
        MatchCommand::AdjustLife {
            player: PlayerId::PlayerOne,
            amount: -100,
        },
        MatchCommand::ResetLife {
            player: PlayerId::PlayerOne,
        },
        MatchCommand::SetBattleStatus {
            status: BattleStatus::PlayerOneAdvantage,
        },
        MatchCommand::SetBattleStatus {
            status: BattleStatus::PlayerTwoAdvantage,
        },
        MatchCommand::SetBattleStatus {
            status: BattleStatus::Even,
        },
        MatchCommand::ToggleTurnAction {
            action: TurnAction::LevelUp,
        },
        MatchCommand::ToggleTurnAction {
            action: TurnAction::Switch,
        },
        MatchCommand::ToggleTurnAction {
            action: TurnAction::Charge,
        },
        MatchCommand::ToggleTurnAction {
            action: TurnAction::Charge,
        },
        MatchCommand::ResetTurnActions,
        MatchCommand::ResetTurnActions,
        MatchCommand::ToggleTurnAction {
            action: TurnAction::Charge,
        },
        MatchCommand::EndTurn,
        MatchCommand::Undo,
        MatchCommand::ResetMatch,
        MatchCommand::Undo,
        MatchCommand::ResetMatch,
    ];
    for _ in 0..55 {
        commands.extend([MatchCommand::EndTurn, MatchCommand::ResetMatch]);
    }
    // Cross the oldest retained baseline, then exercise branching after Undo.
    commands.extend(std::iter::repeat_n(MatchCommand::Undo, 105));
    commands.extend([MatchCommand::EndTurn, MatchCommand::Undo]);
    let mut store = SqliteMatchStore::open_in_memory()?;
    let mut steps = Vec::new();
    for command in commands {
        let changed = store.apply(command)?;
        steps.push(Step {
            command,
            changed,
            state: store.state().clone(),
        });
    }
    let path = std::path::Path::new(&path);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, serde_json::to_string_pretty(&steps)?)?;
    Ok(())
}
