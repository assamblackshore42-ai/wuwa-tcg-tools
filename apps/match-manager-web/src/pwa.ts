import { registerSW } from 'virtual:pwa-register';
import { usePwaStore } from './pwaStore';
import { useMatchStore } from './matchStore';
import { configureUpdateCoordinator, coordinateUpdate } from './updateCoordinator';

let workerRegistration: ServiceWorkerRegistration | undefined;

configureUpdateCoordinator({
  prepare: () => {
    usePwaStore.setState({ applyingUpdate: true, updateDismissed: false, error: null });
    return useMatchStore.getState().prepareUpdate();
  },
  resume: () => {
    useMatchStore.getState().resumeAfterUpdate();
    usePwaStore.setState({ applyingUpdate: false });
  },
  reload: () => window.location.reload(),
});

function notifyUpdate() {
  usePwaStore.setState({ needRefresh: true, updateDismissed: false });
}

// Module initialization runs once, outside React StrictMode effects.
// Development stays free of service workers, as configured in vite.config.ts.
const updateSW = import.meta.env.PROD
  ? registerSW({
      onOfflineReady() {
        usePwaStore.setState({ offlineReady: true, error: null });
      },
      onNeedRefresh: notifyUpdate,
      // Reload only through the coordinator after every participating tab saves.
      onNeedReload: notifyUpdate,
      onRegisteredSW(_url, registration) {
        workerRegistration = registration;
        // onOfflineReady only fires on first installation; an active worker
        // also indicates a completed installation on subsequent visits.
        if (registration?.active) usePwaStore.setState({ offlineReady: true, error: null });
      },
      onRegisterError() {
        usePwaStore.setState({ error: 'オフライン用の準備に失敗しました。' });
      },
    })
  : undefined;

export async function applyPwaUpdate(): Promise<void> {
  if (!updateSW || !usePwaStore.getState().needRefresh || usePwaStore.getState().applyingUpdate)
    return;
  usePwaStore.setState({ applyingUpdate: true, error: null });
  try {
    await coordinateUpdate(async () => {
      const registration = workerRegistration ?? (await navigator.serviceWorker.getRegistration());
      const waiting = registration?.waiting;
      // Another tab may already have activated the version we notified about.
      if (!waiting) {
        if (!registration?.active) throw new Error('更新するアプリを確認できませんでした。');
        return;
      }
      await new Promise<void>((resolve, reject) => {
        const changed = () => {
          if (waiting.state === 'activated' || waiting.state === 'redundant') {
            waiting.removeEventListener('statechange', changed);
            if (waiting.state === 'activated') resolve();
            else reject(new Error('更新に失敗しました。もう一度お試しください。'));
          }
        };
        waiting.addEventListener('statechange', changed);
        void updateSW(true).catch((error: unknown) => {
          waiting.removeEventListener('statechange', changed);
          reject(error);
        });
        changed();
      });
    });
  } catch (error: unknown) {
    usePwaStore.setState({
      applyingUpdate: false,
      error: error instanceof Error ? error.message : '更新できませんでした。',
    });
  }
}
