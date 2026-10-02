import { registerSW } from 'virtual:pwa-register';
import { usePwaStore } from './pwaStore';

function notifyUpdate() {
  usePwaStore.setState({ needRefresh: true, updateDismissed: false });
}

// Module initialization runs once, outside React StrictMode effects.
// Development stays free of service workers, as configured in vite.config.ts.
export const updateSW = import.meta.env.PROD
  ? registerSW({
      onOfflineReady() {
        usePwaStore.setState({ offlineReady: true, error: null });
      },
      onNeedRefresh: notifyUpdate,
      // Keep automatic reloads disabled until save-aware updating is connected.
      onNeedReload: notifyUpdate,
      onRegisteredSW(_url, registration) {
        // onOfflineReady only fires on first installation; an active worker
        // also indicates a completed installation on subsequent visits.
        if (registration?.active) usePwaStore.setState({ offlineReady: true, error: null });
      },
      onRegisterError() {
        usePwaStore.setState({ error: 'オフライン用の準備に失敗しました。' });
      },
    })
  : undefined;
