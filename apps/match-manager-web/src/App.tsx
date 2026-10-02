import { useEffect } from 'react';
import { CircleCheck, LoaderCircle, TriangleAlert } from 'lucide-react';
import {
  LifeCounter,
  BattleStatus,
  TurnManager,
  type BattleStatusValue,
  type TurnAction,
} from '@wuwatcg/match-ui';
import type { ApiBattleStatus, ApiTurnAction } from '@wuwatcg/match-ui/contracts';
import { useMatchStore } from './matchStore';
import { InfoTooltip } from './InfoTooltip';
import { PwaNotice, PwaStatus } from './PwaStatus';
import '@wuwatcg/match-ui/styles.css';
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
  const { match, canUndo, pending, error, updating, initialize, dispatch } = useMatchStore();
  const saveLabel = error ? '保存に失敗' : pending > 0 ? '保存中…' : 'この端末に保存済み';
  useEffect(() => {
    void initialize();
  }, [initialize]);
  return (
    <main className="app-shell web-shell">
      <div className="control-panel">
        <header className="app-header">
          <div className="web-heading">
            <h1>鳴潮対決カウンター</h1>
            <div className="web-heading__indicators">
              {match && (
                <span
                  className={`web-save-status${pending > 0 && !error ? ' is-saving' : ''}${error ? ' is-error' : ''}`}
                  role="status"
                  aria-label="保存状況"
                  title={saveLabel}
                >
                  {error ? (
                    <TriangleAlert aria-hidden="true" size={20} />
                  ) : pending > 0 ? (
                    <LoaderCircle aria-hidden="true" size={20} />
                  ) : (
                    <CircleCheck aria-hidden="true" size={20} />
                  )}
                  <span className="visually-hidden">{saveLabel}</span>
                </span>
              )}
              <PwaStatus />
              <InfoTooltip />
            </div>
          </div>
          <div className="app-header__actions">
            <button
              type="button"
              className="header-action-button"
              disabled={!match || updating}
              onClick={() => {
                if (window.confirm('新しい対戦を開始しますか？')) dispatch({ type: 'reset_match' });
              }}
            >
              新しい対戦
            </button>
            <button
              type="button"
              className="header-action-button"
              disabled={!canUndo || updating}
              onClick={() => dispatch({ type: 'undo' })}
            >
              Undo
            </button>
          </div>
        </header>
        <PwaNotice />
        {error && (
          <div role="alert" className="web-error">
            {error}
            {!match && (
              <button type="button" disabled={updating} onClick={() => void initialize()}>
                再試行
              </button>
            )}
          </div>
        )}
        {!match ? (
          <p role="status">対戦画面を準備しています…</p>
        ) : (
          <fieldset className="web-match-controls" disabled={updating} aria-label="対戦操作">
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
                compact
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
          </fieldset>
        )}
      </div>
    </main>
  );
}
