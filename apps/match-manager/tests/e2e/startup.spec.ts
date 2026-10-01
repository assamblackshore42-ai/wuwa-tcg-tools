import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  const matchState = {
    revision: 0,
    players: [
      { id: 'player_one', name: 'PLAYER 1', life: 20 },
      { id: 'player_two', name: 'PLAYER 2', life: 20 },
    ],
    battleStatus: 'even',
    turn: { number: 1, activePlayer: 'player_one', usedActions: [] },
  };

  await page.route('http://127.0.0.1:38471/api/state', async (route) => {
    await route.fulfill({
      headers: { 'Access-Control-Allow-Origin': 'http://127.0.0.1:1420' },
      json: matchState,
    });
  });
  await page.routeWebSocket('ws://127.0.0.1:38471/ws', (webSocket) => {
    webSocket.send(JSON.stringify(matchState));
  });
});

test('shows the match controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '対戦コントロール' })).toBeVisible();
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('heading', { name: '戦況' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'ターン管理' })).toBeVisible();
  await page.close();
});

test('shared UI preserves the transparent read-only OBS overlay', async ({ page }) => {
  await page.goto('/overlay');
  await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await expect(page.getByLabel('PLAYER 2の現在ライフ')).toHaveText('20');
  await expect(page.getByRole('button')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '対戦コントロール' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '戦況' })).toBeVisible();
  await expect(page.getByLabel('現在のターン')).toHaveText('1');
  const backgrounds = await page.evaluate(() =>
    [document.documentElement, document.body, document.querySelector('.app-shell')!].map(
      (element) => getComputedStyle(element).backgroundColor,
    ),
  );
  expect(backgrounds).toEqual(Array(3).fill('rgba(0, 0, 0, 0)'));
  await page.close();
});
