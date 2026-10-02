import { test, expect } from '@playwright/test';

test('registered worker supports offline reload and keeps the compact layout', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('status', { name: 'オフライン準備', exact: true })).toHaveText(
    'オフラインで利用できます',
  );
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    if (!registration.active) throw new Error('Service worker is not active');
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(700);
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('19');
  // Reload once so that the worker controls the document before going offline.
  await page.reload();
  await expect(page.getByRole('status', { name: 'オフライン準備', exact: true })).toBeVisible();
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('19');
  await expect(page.getByRole('status', { name: 'オフライン準備', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Undo', exact: true })).toBeEnabled();
});

test('registration failure is shown separately from match saving', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.serviceWorker.register = () =>
      Promise.reject(new TypeError('Injected service worker registration failure'));
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('オフライン用の準備に失敗しました');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await page.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }).click();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('19');
  await expect(page.getByRole('status', { name: '保存状況', exact: true })).toHaveText(
    'この端末に保存済み',
  );
  await page.getByRole('button', { name: '閉じる', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
});
