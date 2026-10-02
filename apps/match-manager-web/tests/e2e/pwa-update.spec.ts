import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as base, expect, type Page } from '@playwright/test';

type ReleaseServer = { url: string; publish: () => void };
const test = base.extend<{ releases: ReleaseServer }>({
  releases: async ({ baseURL }, runWithServer) => {
    if (!baseURL) throw new Error('Production preview URL must be configured');
    const dist = fileURLToPath(new URL('../../dist/', import.meta.url));
    const originalHtml = await readFile(resolve(dist, 'index.html'), 'utf8');
    const originalWorker = await readFile(resolve(dist, 'sw.js'), 'utf8');
    let version = 'A';
    const server = createServer((request, response) => {
      void (async () => {
        const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
        const file = resolve(dist, `.${pathname === '/' ? '/index.html' : pathname}`);
        if (!file.startsWith(dist.endsWith(sep) ? dist : dist + sep)) {
          response.writeHead(404).end();
          return;
        }
        const html = originalHtml.replace(
          '<head>',
          `<head><meta name="test-release" content="${version}">`,
        );
        let content: string | Buffer;
        if (pathname === '/' || pathname === '/index.html') content = html;
        else if (pathname === '/sw.js') {
          const revision = createHash('sha256').update(html).digest('hex');
          content = originalWorker.replace(/(url:"index.html",revision:")[^"]+"/, `$1${revision}"`);
          if (content === originalWorker)
            throw new Error('Cannot replace the HTML precache revision');
        } else content = await readFile(file);
        const type = pathname.endsWith('.js')
          ? 'application/javascript'
          : pathname.endsWith('.css')
            ? 'text/css'
            : pathname.endsWith('.wasm')
              ? 'application/wasm'
              : pathname.endsWith('.png')
                ? 'image/png'
                : pathname.endsWith('.webmanifest')
                  ? 'application/manifest+json'
                  : pathname.endsWith('.ico')
                    ? 'image/x-icon'
                    : 'text/html';
        response.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' });
        response.end(content);
      })().catch(() => response.writeHead(404).end());
    });
    await new Promise<void>((resolveListening) => server.listen(0, '127.0.0.1', resolveListening));
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Release server did not start');
    try {
      await runWithServer({
        url: `http://127.0.0.1:${address.port}`,
        publish: () => {
          version = 'B';
        },
      });
    } finally {
      server.closeAllConnections();
      await new Promise<void>((resolveClosed, reject) =>
        server.close((error) => (error ? reject(error) : resolveClosed())),
      );
    }
  },
});

async function openRelease(page: Page, releases: ReleaseServer) {
  await page.goto(releases.url);
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('status', { name: 'オフライン準備', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
}

async function discoverUpdate(page: Page, releases: ReleaseServer) {
  releases.publish();
  await page.evaluate(async () => (await navigator.serviceWorker.getRegistration())!.update());
  await expect(page.getByRole('status', { name: 'アプリの更新', exact: true })).toContainText(
    '新しいバージョン',
  );
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
}

// Keep the actual IndexedDB transaction's completion promise pending. The
// commit has happened, but the session/store must still finish its save queue.
async function holdNextSave(page: Page) {
  await page.evaluate(() => {
    const descriptor = Object.getOwnPropertyDescriptor(IDBTransaction.prototype, 'oncomplete')!;
    let armed = true;
    Object.defineProperty(IDBTransaction.prototype, 'oncomplete', {
      ...descriptor,
      set(handler: ((event: Event) => void) | null) {
        descriptor.set!.call(
          this,
          handler &&
            ((event: Event) => {
              if (armed && this.mode === 'readwrite') {
                armed = false;
                (window as unknown as { releaseSave: () => void }).releaseSave = () =>
                  handler.call(this, event);
              } else handler.call(this, event);
            }),
        );
      },
    });
  });
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect
    .poll(() =>
      page.evaluate(() => typeof (window as unknown as { releaseSave?: () => void }).releaseSave),
    )
    .toBe('function');
  await expect(page.getByRole('status', { name: '保存状況', exact: true })).toHaveText('保存中…');
}

async function releaseSave(page: Page) {
  await page.evaluate(() => (window as unknown as { releaseSave: () => void }).releaseSave());
}

async function expectReleaseB(page: Page, life: string) {
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'B');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText(life);
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeEnabled();
}

test('update waits for saving, rejects new actions and restores Undo', async ({
  page,
  releases,
}) => {
  await openRelease(page, releases);
  await discoverUpdate(page, releases);
  await holdNextSave(page);
  await page.getByRole('button', { name: '更新する', exact: true }).click();
  await expect(page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '新しい対戦', exact: true })).toBeDisabled();
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
  await releaseSave(page);
  await expectReleaseB(page, '19');
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
});

test('all tabs finish saving before updating together', async ({ page, context, releases }) => {
  await openRelease(page, releases);
  const other = await context.newPage();
  await other.goto(releases.url);
  await expect(other.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await discoverUpdate(page, releases);
  await holdNextSave(other);
  await page.getByRole('button', { name: '更新する', exact: true }).click();
  await expect(other.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeDisabled();
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
  await releaseSave(other);
  await expectReleaseB(page, '19');
  await expectReleaseB(other, '19');
});

test('a queued save failure stops the update until a successful save', async ({
  page,
  releases,
}) => {
  await openRelease(page, releases);
  await discoverUpdate(page, releases);
  await page.evaluate(() => {
    const put = IDBObjectStore.prototype.put;
    let failed = false;
    IDBObjectStore.prototype.put = function (...args: Parameters<typeof put>) {
      if (this.name === 'records' && !failed) {
        failed = true;
        throw new DOMException('Injected quota failure', 'QuotaExceededError');
      }
      return put.apply(this, args);
    };
    const increase = document.querySelector<HTMLButtonElement>(
      'button[aria-label="PLAYER 1のライフを1増やす"]',
    )!;
    for (let index = 0; index < 3; index++) increase.click();
    const update = Array.from(document.querySelectorAll('button')).find(
      (button) => button.textContent === '更新する',
    )!;
    update.click();
  });
  await expect(
    page.getByRole('alert').filter({ hasText: '保存エラーがあるため更新を中止' }),
  ).toBeVisible();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('22');
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
  await page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' }).click();
  await expect(page.getByRole('status', { name: '保存状況', exact: true })).toHaveText(
    'この端末に保存済み',
  );
  await page.getByRole('button', { name: '更新する', exact: true }).click();
  await expectReleaseB(page, '23');
});

test('a failed save in another tab cancels the update and resumes both tabs', async ({
  page,
  context,
  releases,
}) => {
  await openRelease(page, releases);
  const other = await context.newPage();
  await other.goto(releases.url);
  await expect(other.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await discoverUpdate(page, releases);
  await other.evaluate(() => {
    const put = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args: Parameters<typeof put>) {
      if (this.name === 'records')
        throw new DOMException('Injected quota failure', 'QuotaExceededError');
      return put.apply(this, args);
    };
  });
  await other.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(other.getByRole('status', { name: '保存状況', exact: true })).toHaveText(
    '保存に失敗',
  );
  await page.getByRole('button', { name: '更新する', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: '他の画面の保存完了を確認できませんでした' }),
  ).toBeVisible();
  await expect(other.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeEnabled();
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
});

test('unresponsive tabs time out without activating the waiting worker', async ({
  page,
  releases,
}) => {
  await openRelease(page, releases);
  await discoverUpdate(page, releases);
  await page.evaluate(() => {
    void navigator.locks.request(
      'wuwa-tcg-match-manager:tabs',
      { mode: 'shared' },
      () =>
        new Promise<void>((resolveLock) => {
          (window as unknown as { releaseUnresponsiveTab: () => void }).releaseUnresponsiveTab =
            resolveLock;
        }),
    );
  });
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          typeof (window as unknown as { releaseUnresponsiveTab?: () => void })
            .releaseUnresponsiveTab,
      ),
    )
    .toBe('function');
  await page.getByRole('button', { name: '更新する', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: '他の画面の保存完了を確認できませんでした' }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' })).toBeEnabled();
  await expect(page.locator('meta[name="test-release"]')).toHaveAttribute('content', 'A');
  expect(
    await page.evaluate(async () =>
      Boolean((await navigator.serviceWorker.getRegistration())?.waiting),
    ),
  ).toBe(true);
  await page.evaluate(() =>
    (window as unknown as { releaseUnresponsiveTab: () => void }).releaseUnresponsiveTab(),
  );
});
