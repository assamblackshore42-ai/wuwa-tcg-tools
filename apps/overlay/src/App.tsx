import { useState } from 'react';

import { BattleStatus, type BattleStatusValue } from './components/BattleStatus';
import { INITIAL_LIFE, LifeCounter } from './components/LifeCounter';
import { TurnManager, type ActivePlayer, type TurnAction } from './components/TurnManager';
import './styles.css';

export function App() {
  const [playerOneLife, setPlayerOneLife] = useState(INITIAL_LIFE);
  const [playerTwoLife, setPlayerTwoLife] = useState(INITIAL_LIFE);
  const [battleStatus, setBattleStatus] = useState<BattleStatusValue>('even');
  const [turn, setTurn] = useState(1);
  const [activePlayer, setActivePlayer] = useState<ActivePlayer>(1);
  const [usedActions, setUsedActions] = useState<Set<TurnAction>>(() => new Set());

  const toggleTurnAction = (action: TurnAction) => {
    setUsedActions((current) => {
      const next = new Set(current);

      if (next.has(action)) {
        next.delete(action);
      } else {
        next.add(action);
      }

      return next;
    });
  };

  const nextTurn = () => {
    setTurn((current) => current + 1);
    setActivePlayer((current) => (current === 1 ? 2 : 1));
    setUsedActions(new Set());
  };

  return (
    <main className="app-shell">
      <div className="control-panel">
        <header className="app-header">
          <div>
            <p className="eyebrow">WUTHERING WAVES TCG</p>
            <h1>対戦コントロール</h1>
          </div>
          <span className="connection-status">
            <span aria-hidden="true" />
            OBS オーバーレイ
          </span>
        </header>

        <div className="life-grid">
          <LifeCounter
            label="PLAYER 1"
            life={playerOneLife}
            onChange={setPlayerOneLife}
            tone="cyan"
          />
          <LifeCounter
            label="PLAYER 2"
            life={playerTwoLife}
            onChange={setPlayerTwoLife}
            tone="magenta"
          />
        </div>

        <div className="match-grid">
          <BattleStatus value={battleStatus} onChange={setBattleStatus} />
          <TurnManager
            turn={turn}
            activePlayer={activePlayer}
            usedActions={usedActions}
            onToggleAction={toggleTurnAction}
            onResetActions={() => setUsedActions(new Set())}
            onNextTurn={nextTurn}
          />
        </div>
      </div>
    </main>
  );
}
