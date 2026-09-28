import { Minus, TrendingUp } from 'lucide-react';

import './BattleStatus.css';

export type BattleStatusValue = 'player-one' | 'even' | 'player-two';

type BattleStatusProps = {
  value: BattleStatusValue;
  onChange: (status: BattleStatusValue) => void;
  readOnly?: boolean;
};

const STATUS_OPTIONS: Array<{
  value: BattleStatusValue;
  label: string;
  shortLabel: string;
}> = [
  { value: 'player-one', label: 'PLAYER 1が優勢', shortLabel: 'P1 優勢' },
  { value: 'even', label: '戦況は互角', shortLabel: '互角' },
  { value: 'player-two', label: 'PLAYER 2が優勢', shortLabel: 'P2 優勢' },
];

export function BattleStatus({ value, onChange, readOnly = false }: BattleStatusProps) {
  const currentLabel =
    STATUS_OPTIONS.find((option) => option.value === value)?.label ?? '戦況は互角';

  return (
    <section
      className={`battle-status battle-status--${value}`}
      aria-labelledby="battle-status-title"
    >
      <header className="battle-status__header">
        <div>
          <p className="section-kicker">BATTLE STATUS</p>
          <h2 id="battle-status-title">戦況</h2>
        </div>
        <div className="battle-status__current" aria-live="polite">
          {value === 'even' ? <Minus aria-hidden="true" /> : <TrendingUp aria-hidden="true" />}
          <span>{currentLabel}</span>
        </div>
      </header>

      {!readOnly && (
        <div className="battle-status__options" role="group" aria-label="戦況を選択">
          {STATUS_OPTIONS.map((option) => (
            <button
              className={value === option.value ? 'is-active' : undefined}
              type="button"
              key={option.value}
              onClick={() => onChange(option.value)}
              aria-pressed={value === option.value}
            >
              {option.shortLabel}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
