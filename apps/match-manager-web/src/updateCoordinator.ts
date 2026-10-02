// A shared lease represents an open match tab. Updating needs the exclusive
// lease, so even a suspended tab must finish saving (or close) before activation.
const TAB_LOCK = 'wuwa-tcg-match-manager:tabs';
const UPDATE_LOCK = 'wuwa-tcg-match-manager:update';
const CHANNEL = 'wuwa-tcg-match-manager:update';
const PREPARE_TIMEOUT = 15_000;

type Callbacks = {
  prepare: () => Promise<void>;
  resume: () => void;
  reload: () => void;
};
type Message = { type: 'prepare' | 'cancel' | 'failed'; id: string };
let callbacks: Callbacks | undefined;
let channel: BroadcastChannel | undefined;
let currentId: string | undefined;
let cancelUpdate: (() => void) | undefined;
let lease: { ready: Promise<void>; release: () => void } | undefined;

export function ensureTabLease(): Promise<void> {
  if (!navigator.locks) return Promise.resolve();
  if (lease) return lease.ready;
  let release!: () => void;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  let ready!: () => void;
  let failed!: (error: unknown) => void;
  const acquired = new Promise<void>((resolve, reject) => {
    ready = resolve;
    failed = reject;
  });
  const nextLease = { ready: acquired, release };
  lease = nextLease;
  void navigator.locks
    .request(TAB_LOCK, { mode: 'shared' }, async () => {
      ready();
      await released;
    })
    .catch(failed);
  return acquired;
}

function releaseTabLease() {
  lease?.release();
  lease = undefined;
}

async function resume(id: string) {
  if (currentId !== id) return;
  await ensureTabLease();
  if (currentId !== id) return;
  currentId = undefined;
  callbacks?.resume();
}

async function preparePeer(id: string) {
  if (!callbacks || currentId) return;
  currentId = id;
  try {
    // prepare() blocks new actions synchronously, before its first await.
    const drained = callbacks.prepare();
    void drained.catch(() => {});
    const previousWorker = (await navigator.serviceWorker.getRegistration())?.active;
    await drained;
    if (currentId !== id) return;
    releaseTabLease();
    await ensureTabLease();
    if (currentId !== id) return;
    const activeWorker = (await navigator.serviceWorker.getRegistration())?.active;
    if (previousWorker && activeWorker && activeWorker !== previousWorker) {
      callbacks.reload();
    } else {
      await resume(id);
    }
  } catch {
    channel?.postMessage({ type: 'failed', id } satisfies Message);
    await resume(id);
  }
}

export function configureUpdateCoordinator(next: Callbacks) {
  callbacks = next;
  if (!navigator.locks || typeof BroadcastChannel === 'undefined' || channel) return;
  channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = (event: MessageEvent<unknown>) => {
    const message = event.data as Partial<Message> | null;
    if (!message || typeof message.id !== 'string') return;
    if (message.type === 'prepare') void preparePeer(message.id);
    if (message.type === 'cancel') void resume(message.id);
    if (message.type === 'failed' && currentId === message.id) cancelUpdate?.();
  };
}

export async function coordinateUpdate(activate: () => Promise<void>) {
  if (!callbacks || !channel || !navigator.locks) {
    throw new Error(
      'このブラウザでは更新前の保存確認ができません。すべてのタブを閉じて、アプリを開き直してください。',
    );
  }
  await ensureTabLease();
  await navigator.locks.request(UPDATE_LOCK, { ifAvailable: true }, async (lock) => {
    if (!lock || currentId) throw new Error('別の画面で更新を準備しています。');
    const id = crypto.randomUUID();
    currentId = id;
    const abort = new AbortController();
    cancelUpdate = () => abort.abort();
    const timeout = window.setTimeout(() => abort.abort(), PREPARE_TIMEOUT);
    const cancelled = new Promise<never>((_resolve, reject) => {
      abort.signal.addEventListener('abort', () => reject(abort.signal.reason), { once: true });
    });
    // Queue the exclusive request BEFORE any tab releases its shared lease.
    // New/rejoining tabs cannot start a match until activation finishes.
    const exclusive = navigator.locks.request(TAB_LOCK, { signal: abort.signal }, async () => {
      window.clearTimeout(timeout);
      await activate();
    });
    // Avoid an unhandled rejection if a peer fails while local saving continues.
    void exclusive.catch(() => {});
    channel!.postMessage({ type: 'prepare', id } satisfies Message);
    try {
      await Promise.race([callbacks!.prepare(), cancelled]);
      releaseTabLease();
      await exclusive;
      await ensureTabLease();
      callbacks!.reload();
    } catch (error) {
      abort.abort();
      await exclusive.catch(() => {});
      channel!.postMessage({ type: 'cancel', id } satisfies Message);
      await resume(id);
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error(
          '他の画面の保存完了を確認できませんでした。保存エラーを解消し、応答しないタブを閉じてから再試行してください。',
          { cause: error },
        );
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
      cancelUpdate = undefined;
    }
  });
}
