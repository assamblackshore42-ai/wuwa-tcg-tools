import {
  ArrowLeftRight,
  Check,
  ChevronRight,
  Music,
  RotateCcw,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

import './TurnManager.css';

export type TurnAction = 'level-up' | 'switch' | 'charge';
export type ActivePlayer = 1 | 2;

type TurnManagerProps = {
  turn: number;
  activePlayer: ActivePlayer;
  usedActions: ReadonlySet<TurnAction>;
  onToggleAction: (action: TurnAction) => void;
  onResetActions: () => void;
  onNextTurn: () => void;
};

const TURN_ACTIONS: Array<{
  id: TurnAction;
  label: string;
  description: string;
  icon: LucideIcon;
}> = [
  { id: 'level-up', label: 'レベルアップ', description: 'このターンに使用済み', icon: Sparkles },
  { id: 'switch', label: '切り替え', description: 'このターンに使用済み', icon: ArrowLeftRight },
  { id: 'charge', label: 'チャージ', description: 'このターンに使用済み', icon: Music },
];

export function TurnManager({
  turn,
  activePlayer,
  usedActions,
  onToggleAction,
  onResetActions,
  onNextTurn,
}: TurnManagerProps) {
  return (
    <section className="turn-manager" aria-labelledby="turn-manager-title">
      <header className="turn-manager__header">
        <div>
          <p className="section-kicker">TURN MANAGEMENT</p>
          <h2 id="turn-manager-title">ターン管理</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={onResetActions}
          aria-label="ターン内行動をリセット"
          title="行動をリセット"
        >
          <RotateCcw aria-hidden="true" size={18} />
        </button>
      </header>

      <div className="turn-manager__summary">
        <div className="turn-manager__number">
          <span>TURN</span>
          <output aria-label="現在のターン">{turn}</output>
        </div>
        <div className={`turn-manager__active turn-manager__active--player-${activePlayer}`}>
          <span>現在の手番</span>
          <strong>PLAYER {activePlayer}</strong>
        </div>
        <button className="turn-manager__next" type="button" onClick={onNextTurn}>
          ターン終了
          <ChevronRight aria-hidden="true" />
        </button>
      </div>

      <div className="turn-manager__actions" aria-label="ターン内行動">
        {TURN_ACTIONS.map(({ id, label, description, icon: Icon }) => {
          const isUsed = usedActions.has(id);

          return (
            <button
              className={isUsed ? 'is-used' : undefined}
              type="button"
              key={id}
              onClick={() => onToggleAction(id)}
              aria-pressed={isUsed}
              aria-label={`${label}を${isUsed ? '未使用に戻す' : '使用済みにする'}`}
            >
              <span className="turn-manager__action-icon">
                {isUsed ? <Check aria-hidden="true" /> : <Icon aria-hidden="true" />}
              </span>
              <span>
                <strong>{label}</strong>
                <small>{isUsed ? description : '未使用'}</small>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
