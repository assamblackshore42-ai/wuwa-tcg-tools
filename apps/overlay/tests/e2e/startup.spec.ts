import { expect, test } from '@playwright/test';

test('shows the setup confirmation', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '環境構築が完了しました' })).toBeVisible();
});
