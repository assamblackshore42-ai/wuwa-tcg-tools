import { expect, test } from '@playwright/test';

test('shows the match controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '対戦コントロール' })).toBeVisible();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('heading', { name: '戦況' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'ターン管理' })).toBeVisible();
});
