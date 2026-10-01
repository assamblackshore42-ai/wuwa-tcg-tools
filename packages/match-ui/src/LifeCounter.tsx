import { Minus, Plus } from 'lucide-react';

import './LifeCounter.css';

type LifeCounterProps = {
  label: string;
  life: number;
  onAdjust: (amount: -1 | 1) => void;
  tone: 'cyan' | 'magenta';
  readOnly?: boolean;
};

export function LifeCounter({
  label,
  life,
  onAdjust,
  tone,
  readOnly = false,
}: LifeCounterProps) {
  return (
    <section
      className={`life-counter life-counter--${tone}${readOnly ? ' life-counter--readonly' : ''}`}
      aria-label={`${label}のライフ`}
    >
      <header className="life-counter__header">
        <div>
          <p className="section-kicker">LIFE POINT</p>
          <h2>{label}</h2>
        </div>
      </header>

      <div className="life-counter__controls">
        {!readOnly && (
          <button
            type="button"
            onClick={() => onAdjust(-1)}
            aria-label={`${label}のライフを1減らす`}
          >
            <Minus aria-hidden="true" />
          </button>
        )}
        <output
          className="life-counter__value"
          aria-live="polite"
          aria-label={`${label}の現在ライフ`}
        >
          {life}
        </output>
        {!readOnly && (
          <button
            type="button"
            onClick={() => onAdjust(1)}
            aria-label={`${label}のライフを1増やす`}
          >
            <Plus aria-hidden="true" />
          </button>
        )}
      </div>
    </section>
  );
}
