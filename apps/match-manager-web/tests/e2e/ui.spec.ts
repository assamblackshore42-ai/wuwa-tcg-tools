import { test, expect } from '@playwright/test';

test('mobile-sized UI operates with Wasm and never connects to Desktop', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  const desktopRequests: string[] = [];
  const wasmResponses: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (request.url().includes(':38471')) desktopRequests.push(request.url());
  });
  page.on('websocket', (socket) => {
    if (socket.url().includes(':38471')) desktopRequests.push(socket.url());
  });
  page.on('response', (response) => {
    if (response.url().includes('.wasm') && response.ok()) wasmResponses.push(response.url());
  });
  await page.goto('/');
  const life = page.getByLabel('PLAYER 1の現在ライフ');
  await expect(life).toHaveText('20');
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(life).toHaveText('19');
  await page.getByRole('button', { name: 'P2 優勢', exact: true }).click();
  await expect(page.getByText('PLAYER 2が優勢', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'チャージを使用済みにする' }).click();
  await page.getByRole('button', { name: 'ターン終了' }).click();
  await expect(page.getByLabel('現在のターン')).toHaveText('2');
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(page.getByLabel('現在のターン')).toHaveText('1');
  await expect(page.getByRole('button', { name: 'チャージを未使用に戻す' })).toBeVisible();
  page.once('dialog', (dialog) => dialog.dismiss());
  await page.getByRole('button', { name: '新しい対戦' }).click();
  await expect(life).toHaveText('19');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '新しい対戦' }).click();
  await expect(life).toHaveText('20');
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(life).toHaveText('19');
  await expect(page.getByRole('status', { name: '保存状況' })).toHaveText('この端末に保存済み');
  await page.reload();
  await expect(life).toHaveText('19');
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeEnabled();
  expect(wasmResponses.length).toBeGreaterThan(0);
  expect(desktopRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test('a failed rapid tap remains visible while already queued later taps commit', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await page.evaluate(() => {
    const put = IDBObjectStore.prototype.put;
    let failed = false;
    IDBObjectStore.prototype.put = function (...args: Parameters<typeof put>) {
      if (this.name === 'records' && !failed) {
        failed = true;
        throw new DOMException('injected failure', 'QuotaExceededError');
      }
      return put.apply(this, args);
    };
    const button = document.querySelector<HTMLButtonElement>(
      'button[aria-label="PLAYER 1のライフを1増やす"]',
    )!;
    for (let index = 0; index < 3; index++) button.click();
  });
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('22');
  await expect(page.getByRole('status', { name: '保存状況' })).toHaveText('保存に失敗');
  await expect(page.getByRole('alert')).toContainText('空き容量が不足');
  await page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('23');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('failed Wasm loading offers retry', async ({ page }) => {
  await page.route('**/*.wasm*', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('起動できませんでした');
  await page.unroute('**/*.wasm*');
  await page.getByRole('button', { name: '再試行' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
});

test('storage unavailable shows an error instead of falling back to unsaved memory', async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'indexedDB', { value: undefined });
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('起動できませんでした');
  await expect(page.getByRole('button', { name: '再試行' })).toBeVisible();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveCount(0);
});

test('quota failure keeps UI and saved state unchanged, then succeeds on retry', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await page.evaluate(() => {
    const put = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args: Parameters<typeof put>) {
      if (this.name === 'records') throw new DOMException('injected failure', 'QuotaExceededError');
      return put.apply(this, args);
    };
  });
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(page.getByRole('alert')).toContainText('空き容量が不足');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('19');
  await expect(page.getByRole('alert')).toHaveCount(0);
});
