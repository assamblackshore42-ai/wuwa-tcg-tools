import { useState } from 'react';

import { BattleStatus, type BattleStatusValue } from './components/BattleStatus';
import { INITIAL_LIFE, LifeCounter } from './components/LifeCounter';
import './styles.css';

export function App() {
  const [playerOneLife, setPlayerOneLife] = useState(INITIAL_LIFE);
  const [playerTwoLife, setPlayerTwoLife] = useState(INITIAL_LIFE);
  const [battleStatus, setBattleStatus] = useState<BattleStatusValue>('even');

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
        </div>
      </div>
    </main>
  );
}
