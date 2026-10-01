import type { MatchCommand, MatchState } from '@wuwatcg/match-ui/contracts';
export type {
  PlayerId,
  ApiBattleStatus,
  ApiTurnAction,
  MatchState,
  MatchCommand,
} from '@wuwatcg/match-ui/contracts';

type CommandResponse = {
  changed: boolean;
  state: MatchState;
};

const HTTP_BASE = 'http://127.0.0.1:38471';
export const OBS_OVERLAY_URL = `${HTTP_BASE}/overlay`;
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
