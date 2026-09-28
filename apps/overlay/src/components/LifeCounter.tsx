import { Minus, Plus, RotateCcw } from 'lucide-react';

import './LifeCounter.css';

export const INITIAL_LIFE = 20;
export const MIN_LIFE = 0;
export const MAX_LIFE = 999;

type LifeCounterProps = {
  label: string;
  life: number;
  onChange: (life: number) => void;
  tone: 'cyan' | 'magenta';
};

export function LifeCounter({ label, life, onChange, tone }: LifeCounterProps) {
  const setLife = (nextLife: number) => {
    onChange(Math.min(MAX_LIFE, Math.max(MIN_LIFE, nextLife)));
  };

  return (
    <section className={`life-counter life-counter--${tone}`} aria-label={`${label}のライフ`}>
      <header className="life-counter__header">
        <div>
          <p className="section-kicker">LIFE POINT</p>
          <h2>{label}</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={() => setLife(INITIAL_LIFE)}
          aria-label={`${label}のライフを${INITIAL_LIFE}に戻す`}
          title="初期値に戻す"
        >
          <RotateCcw aria-hidden="true" size={18} />
        </button>
      </header>

      <div className="life-counter__controls">
        <button
          type="button"
          onClick={() => setLife(life - 1)}
          aria-label={`${label}のライフを1減らす`}
        >
          <Minus aria-hidden="true" />
        </button>
        <output
          className="life-counter__value"
          aria-live="polite"
          aria-label={`${label}の現在ライフ`}
        >
          {life}
        </output>
        <button
          type="button"
          onClick={() => setLife(life + 1)}
          aria-label={`${label}のライフを1増やす`}
        >
          <Plus aria-hidden="true" />
        </button>
      </div>
    </section>
  );
}
