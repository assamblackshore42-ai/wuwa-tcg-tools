export type PlayerId = 'player_one' | 'player_two';
export type ApiBattleStatus = 'player_one_advantage' | 'even' | 'player_two_advantage';
export type ApiTurnAction = 'level_up' | 'switch' | 'charge';

export type MatchState = {
  revision: number;
  players: [
    { id: 'player_one'; name: string; life: number },
    { id: 'player_two'; name: string; life: number },
  ];
  battleStatus: ApiBattleStatus;
  turn: {
    number: number;
    activePlayer: PlayerId;
    usedActions: ApiTurnAction[];
  };
};

export type MatchCommand =
  | { type: 'adjust_life'; player: PlayerId; amount: number }
  | { type: 'set_life'; player: PlayerId; life: number }
  | { type: 'reset_life'; player: PlayerId }
  | { type: 'set_battle_status'; status: ApiBattleStatus }
  | { type: 'toggle_turn_action'; action: ApiTurnAction }
  | { type: 'reset_turn_actions' }
  | { type: 'end_turn' }
  | { type: 'reset_match' }
  | { type: 'undo' };
