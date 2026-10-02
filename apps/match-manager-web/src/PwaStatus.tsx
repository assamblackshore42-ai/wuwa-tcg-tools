import { CloudCheck } from 'lucide-react';
import { usePwaStore } from './pwaStore';

export function PwaStatus() {
  const offlineReady = usePwaStore((state) => state.offlineReady);
  if (!offlineReady) return null;
  return (
    <span
      className="web-pwa-status"
      role="status"
      aria-label="オフライン準備"
      title="オフラインで利用できます"
    >
      <CloudCheck aria-hidden="true" size={20} />
      <span className="visually-hidden">オフラインで利用できます</span>
    </span>
  );
}

export function PwaNotice() {
  const { needRefresh, updateDismissed, error } = usePwaStore();
  return (
    <>
      {needRefresh && !updateDismissed && (
        <div className="web-pwa-notice" role="status" aria-label="アプリの更新">
          <span>新しいバージョンがあります</span>
          <button
            type="button"
            className="header-action-button"
            onClick={() => usePwaStore.setState({ updateDismissed: true })}
          >
            あとで
          </button>
        </div>
      )}
      {error && (
        <div className="web-error" role="alert">
          {error}
          <button type="button" onClick={() => usePwaStore.setState({ error: null })}>
            閉じる
          </button>
        </div>
      )}
    </>
  );
}
