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
  await page.reload();
  await expect(life).toHaveText('20');
  expect(wasmResponses.length).toBeGreaterThan(0);
  expect(desktopRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test('failed Wasm loading offers retry', async ({ page }) => {
  await page.route('**/*.wasm*', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('起動できませんでした');
  await page.unroute('**/*.wasm*');
  await page.getByRole('button', { name: '再試行' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
});
