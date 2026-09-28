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

type CommandResponse = {
  changed: boolean;
  state: MatchState;
};

const HTTP_BASE = 'http://127.0.0.1:38471';
export const MATCH_WEB_SOCKET_URL = 'ws://127.0.0.1:38471/ws';

export async function fetchMatchState(): Promise<MatchState> {
  const response = await fetch(`${HTTP_BASE}/api/state`);
  return readJsonResponse<MatchState>(response);
}

export async function postMatchCommand(command: MatchCommand): Promise<CommandResponse> {
  const response = await fetch(`${HTTP_BASE}/api/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  });
  return readJsonResponse<CommandResponse>(response);
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new Error(payload?.error ?? `ローカルサーバーがHTTP ${response.status}を返しました`);
  }

  return (await response.json()) as T;
}
