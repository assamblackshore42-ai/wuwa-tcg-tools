import { useEffect, useRef, useState } from 'react';
import { Info } from 'lucide-react';

export function InfoTooltip() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  return (
    <div
      ref={root}
      className="web-info"
      onPointerEnter={(event) => {
        if (event.pointerType === 'mouse') setOpen(true);
      }}
      onPointerLeave={(event) => {
        if (event.pointerType === 'mouse') setOpen(false);
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="icon-button"
        aria-label="保存について"
        aria-expanded={open}
        aria-describedby={open ? 'storage-info' : undefined}
        onClick={() => setOpen((value) => !value)}
        onFocus={(event) => {
          if (event.currentTarget.matches(':focus-visible')) setOpen(true);
        }}
      >
        <Info aria-hidden="true" size={20} />
      </button>
      {open && (
        <div id="storage-info" role="tooltip" className="web-info__tooltip">
          対戦状態はこの端末に保存されます。ブラウザのデータ削除や空き容量不足などで失われる場合があります。
        </div>
      )}
    </div>
  );
}
