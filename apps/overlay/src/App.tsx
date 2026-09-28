import { useEffect } from 'react';

import type { ApiBattleStatus, ApiTurnAction, MatchCommand } from './api/matchApi';
import { BattleStatus, type BattleStatusValue } from './components/BattleStatus';
import { LifeCounter } from './components/LifeCounter';
import { TurnManager, type ActivePlayer, type TurnAction } from './components/TurnManager';
import { useMatchStore, type ConnectionStatus } from './store/matchStore';
import './styles.css';

const BATTLE_STATUS_TO_UI: Record<ApiBattleStatus, BattleStatusValue> = {
  player_one_advantage: 'player-one',
  even: 'even',
  player_two_advantage: 'player-two',
};

const BATTLE_STATUS_TO_API: Record<BattleStatusValue, ApiBattleStatus> = {
  'player-one': 'player_one_advantage',
  even: 'even',
  'player-two': 'player_two_advantage',
};

const TURN_ACTION_TO_UI: Record<ApiTurnAction, TurnAction> = {
  level_up: 'level-up',
  switch: 'switch',
  charge: 'charge',
};

const TURN_ACTION_TO_API: Record<TurnAction, ApiTurnAction> = {
  'level-up': 'level_up',
  switch: 'switch',
  charge: 'charge',
};

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connecting: '接続中',
  connected: '同期中',
  reconnecting: '再接続中',
  error: '接続エラー',
};

export function App() {
  const isOverlay = window.location.pathname === '/overlay';
  const match = useMatchStore((store) => store.match);
  const connectionStatus = useMatchStore((store) => store.connectionStatus);
  const error = useMatchStore((store) => store.error);
  const connect = useMatchStore((store) => store.connect);
  const sendCommand = useMatchStore((store) => store.sendCommand);

  useEffect(() => connect(), [connect]);

  const dispatch = (command: MatchCommand) => {
    void sendCommand(command);
  };

  return (
    <main className={`app-shell${isOverlay ? ' app-shell--overlay' : ''}`}>
      <div className={`control-panel${isOverlay ? ' overlay-panel' : ''}`}>
        {!isOverlay && (
          <header className="app-header">
            <div>
              <p className="eyebrow">WUTHERING WAVES TCG</p>
              <h1>対戦コントロール</h1>
            </div>
            <span className={`connection-status connection-status--${connectionStatus}`}>
              <span aria-hidden="true" />
              {STATUS_LABELS[connectionStatus]}
            </span>
          </header>
        )}

        {!isOverlay && error !== null && <p className="connection-error">{error}</p>}
        {isOverlay && connectionStatus !== 'connected' && (
          <p className="overlay-connection-status">{STATUS_LABELS[connectionStatus]}</p>
        )}

        {match === null ? (
          <section className="loading-state" aria-live="polite">
            ローカルサーバーから対戦状態を読み込んでいます…
          </section>
        ) : (
          <>
            <div className="life-grid">
              {match.players.map((player, index) => (
                <LifeCounter
                  key={player.id}
                  label={player.name}
                  life={player.life}
                  onAdjust={(amount) =>
                    dispatch({ type: 'adjust_life', player: player.id, amount })
                  }
                  onReset={() => dispatch({ type: 'reset_life', player: player.id })}
                  tone={index === 0 ? 'cyan' : 'magenta'}
                  readOnly={isOverlay}
                />
              ))}
            </div>

            <div className="match-grid">
              <BattleStatus
                value={BATTLE_STATUS_TO_UI[match.battleStatus]}
                onChange={(status) =>
                  dispatch({ type: 'set_battle_status', status: BATTLE_STATUS_TO_API[status] })
                }
                readOnly={isOverlay}
              />
              <TurnManager
                turn={match.turn.number}
                activePlayer={(match.turn.activePlayer === 'player_one' ? 1 : 2) as ActivePlayer}
                usedActions={
                  new Set(match.turn.usedActions.map((action) => TURN_ACTION_TO_UI[action]))
                }
                onToggleAction={(action) =>
                  dispatch({ type: 'toggle_turn_action', action: TURN_ACTION_TO_API[action] })
                }
                onResetActions={() => dispatch({ type: 'reset_turn_actions' })}
                onNextTurn={() => dispatch({ type: 'end_turn' })}
                readOnly={isOverlay}
              />
            </div>
          </>
        )}
      </div>
    </main>
  );
}
