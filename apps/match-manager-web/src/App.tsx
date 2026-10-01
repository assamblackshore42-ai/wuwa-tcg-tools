import { useEffect } from 'react';
import { LifeCounter } from '../../match-manager/src/components/LifeCounter';
import {
  BattleStatus,
  type BattleStatusValue,
} from '../../match-manager/src/components/BattleStatus';
import { TurnManager, type TurnAction } from '../../match-manager/src/components/TurnManager';
import type { ApiBattleStatus, ApiTurnAction } from '../../match-manager/src/api/matchApi';
import { useMatchStore } from './matchStore';
import '../../match-manager/src/styles.css';
import './web.css';

const battleToUI: Record<ApiBattleStatus, BattleStatusValue> = {
  player_one_advantage: 'player-one',
  even: 'even',
  player_two_advantage: 'player-two',
};
const battleToAPI: Record<BattleStatusValue, ApiBattleStatus> = {
  'player-one': 'player_one_advantage',
  even: 'even',
  'player-two': 'player_two_advantage',
};
const actionToUI: Record<ApiTurnAction, TurnAction> = {
  level_up: 'level-up',
  switch: 'switch',
  charge: 'charge',
};
const actionToAPI: Record<TurnAction, ApiTurnAction> = {
  'level-up': 'level_up',
  switch: 'switch',
  charge: 'charge',
};

export function App() {
  const { match, canUndo, pending, error, initialize, dispatch } = useMatchStore();
  useEffect(() => {
    void initialize();
  }, [initialize]);
  return (
    <main className="app-shell web-shell">
      <div className="control-panel">
        <header className="app-header">
          <div>
            <p className="eyebrow">WUTHERING WAVES TCG</p>
            <h1>対戦コントロール</h1>
          </div>
          <div className="app-header__actions">
            <button
              type="button"
              className="header-action-button"
              disabled={!match}
              onClick={() => {
                if (window.confirm('新しい対戦を開始しますか？')) dispatch({ type: 'reset_match' });
              }}
            >
              新しい対戦
            </button>
            <button
              type="button"
              className="header-action-button"
              disabled={!canUndo}
              onClick={() => dispatch({ type: 'undo' })}
            >
              Undo
            </button>
          </div>
        </header>
        <p className="web-notice">
          対戦状態はこの端末に保存されます。ブラウザのデータを削除すると消去されます。
        </p>
        {match && (
          <p className="web-notice" role="status" aria-label="保存状況">
            {pending > 0 ? '保存中…' : 'この端末に保存済み'}
          </p>
        )}
        {error && (
          <div role="alert" className="connection-error">
            {error}
            {!match && (
              <button type="button" onClick={() => void initialize()}>
                再試行
              </button>
            )}
          </div>
        )}
        {!match ? (
          <p role="status">対戦画面を準備しています…</p>
        ) : (
          <>
            <div className="life-grid">
              {match.players.map((player, index) => (
                <LifeCounter
                  key={player.id}
                  label={player.name}
                  life={player.life}
                  tone={index === 0 ? 'cyan' : 'magenta'}
                  onAdjust={(amount) =>
                    dispatch({ type: 'adjust_life', player: player.id, amount })
                  }
                  onReset={() => dispatch({ type: 'reset_life', player: player.id })}
                />
              ))}
            </div>
            <div className="match-grid">
              <BattleStatus
                value={battleToUI[match.battleStatus]}
                onChange={(status) =>
                  dispatch({ type: 'set_battle_status', status: battleToAPI[status] })
                }
              />
              <TurnManager
                turn={match.turn.number}
                activePlayer={match.turn.activePlayer === 'player_one' ? 1 : 2}
                usedActions={new Set(match.turn.usedActions.map((action) => actionToUI[action]))}
                onToggleAction={(action) =>
                  dispatch({ type: 'toggle_turn_action', action: actionToAPI[action] })
                }
                onResetActions={() => dispatch({ type: 'reset_turn_actions' })}
                onNextTurn={() => dispatch({ type: 'end_turn' })}
              />
            </div>
          </>
        )}
      </div>
    </main>
  );
}
