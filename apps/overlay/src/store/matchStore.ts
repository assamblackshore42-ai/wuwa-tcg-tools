import { create } from 'zustand';

import {
  MATCH_WEB_SOCKET_URL,
  fetchMatchState,
  postMatchCommand,
  type MatchCommand,
  type MatchState,
} from '../api/matchApi';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'error';

type MatchStore = {
  match: MatchState | null;
  connectionStatus: ConnectionStatus;
  error: string | null;
  connect: () => () => void;
  sendCommand: (command: MatchCommand) => Promise<void>;
};

const RECONNECT_DELAY_MS = 1_500;

export const useMatchStore = create<MatchStore>((set, get) => ({
  match: null,
  connectionStatus: 'connecting',
  error: null,

  connect: () => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const acceptState = (incoming: MatchState) => {
      const current = get().match;
      if (current === null || incoming.revision >= current.revision) {
        set({ match: incoming, error: null });
      }
    };

    const openSocket = () => {
      if (stopped) return;

      socket = new WebSocket(MATCH_WEB_SOCKET_URL);
      socket.onopen = () => {
        if (!stopped) set({ connectionStatus: 'connected', error: null });
      };
      socket.onmessage = (event) => {
        if (typeof event.data !== 'string') return;

        try {
          acceptState(JSON.parse(event.data) as MatchState);
        } catch {
          set({ error: 'サーバーから不正な状態データを受信しました' });
        }
      };
      socket.onerror = () => {
        if (!stopped) set({ connectionStatus: 'error', error: 'サーバーへ接続できません' });
      };
      socket.onclose = () => {
        if (stopped) return;
        set({ connectionStatus: 'reconnecting' });
        reconnectTimer = setTimeout(openSocket, RECONNECT_DELAY_MS);
      };
    };

    set({ connectionStatus: 'connecting', error: null });
    void fetchMatchState()
      .then(acceptState)
      .catch((error: unknown) => {
        if (!stopped) {
          set({
            connectionStatus: 'error',
            error: error instanceof Error ? error.message : '対戦状態を取得できません',
          });
        }
      });
    openSocket();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      socket?.close();
    };
  },

  sendCommand: async (command) => {
    try {
      const response = await postMatchCommand(command);
      const current = get().match;
      if (current === null || response.state.revision >= current.revision) {
        set({ match: response.state, error: null });
      }
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : '操作を送信できません' });
    }
  },
}));
