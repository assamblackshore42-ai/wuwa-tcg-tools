import { test, expect } from '@playwright/test';

for (const width of [320, 390, 430]) {
  test.describe(`portrait ${width}px`, () => {
    test.use({
      viewport: { width, height: width === 320 ? 700 : 844 },
      isMobile: true,
      hasTouch: true,
    });

    test('touch controls fit, save repeated taps and restore after reload', async ({ page }) => {
      await page.goto('/');
      const life = page.getByLabel('PLAYER 1の現在ライフ');
      await expect(life).toHaveText('20');
      const first = await page.getByRole('region', { name: 'PLAYER 1のライフ' }).boundingBox();
      const second = await page.getByRole('region', { name: 'PLAYER 2のライフ' }).boundingBox();
      expect(first!.y).toBe(second!.y);
      expect(first!.x + first!.width).toBeLessThan(second!.x);
      const smallTargets = await page.getByRole('button').evaluateAll((buttons) =>
        buttons
          .filter((button) => {
            const rect = button.getBoundingClientRect();
            return rect.width < 44 || rect.height < 44;
          })
          .map((button) => button.getAttribute('aria-label') ?? button.textContent),
      );
      expect(smallTargets).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      const endTurnBox = await page.getByRole('button', { name: 'ターン終了' }).boundingBox();
      expect(endTurnBox!.y + endTurnBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
      expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(
        page.viewportSize()!.height,
      );
      for (let index = 0; index < 12; index++) {
        await page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' }).tap();
      }
      await expect(life).toHaveText('32');
      await page.getByRole('button', { name: 'PLAYER 2のライフを1減らす' }).tap();
      await expect(page.getByLabel('PLAYER 2の現在ライフ')).toHaveText('19');
      await page.getByRole('button', { name: 'P1 優勢', exact: true }).tap();
      await page.getByRole('button', { name: 'チャージを使用済みにする' }).tap();
      await page.getByRole('button', { name: 'ターン終了' }).tap();
      await expect(page.getByLabel('現在のターン')).toHaveText('2');
      await page.getByRole('button', { name: 'Undo', exact: true }).tap();
      await expect(page.getByRole('button', { name: 'チャージを未使用に戻す' })).toBeVisible();
      await page.reload();
      await expect(life).toHaveText('32');
      await expect(page.getByLabel('PLAYER 2の現在ライフ')).toHaveText('19');
      await expect(page.getByRole('button', { name: 'P1 優勢', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      await expect(page.getByRole('button', { name: 'チャージを未使用に戻す' })).toBeVisible();
      await page.screenshot({ path: test.info().outputPath('portrait.png'), fullPage: true });
    });

    test('info tooltip opens by touch without adding height and dismisses outside', async ({
      page,
    }) => {
      await page.goto('/');
      await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
      const info = page.getByRole('button', { name: '保存について' });
      await expect(page.getByRole('tooltip')).toHaveCount(0);
      const before = await page.getByRole('button', { name: 'ターン終了' }).boundingBox();
      await info.tap();
      await expect(page.getByRole('tooltip')).toContainText('ブラウザのデータを削除すると消去');
      await expect(info).toHaveAttribute('aria-expanded', 'true');
      expect(await page.getByRole('button', { name: 'ターン終了' }).boundingBox()).toEqual(before);
      await page.getByRole('heading', { name: '鳴潮対決カウンター' }).tap();
      await expect(page.getByRole('tooltip')).toHaveCount(0);
      await info.tap();
      await expect(page.getByRole('tooltip')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('tooltip')).toHaveCount(0);
    });

    test('safe-area padding and reduced motion preserve usable controls', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto('/');
      await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
      await expect(page.locator('meta[name="viewport"]')).toHaveAttribute(
        'content',
        /viewport-fit=cover/,
      );
      await page.locator('.web-shell').evaluate((element) => {
        const shell = element as HTMLElement;
        shell.style.setProperty('--safe-area-top', '24px');
        shell.style.setProperty('--safe-area-right', '12px');
        shell.style.setProperty('--safe-area-bottom', '34px');
        shell.style.setProperty('--safe-area-left', '12px');
      });
      const padding = await page.locator('.web-shell').evaluate((element) => {
        const style = getComputedStyle(element);
        return [style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft];
      });
      expect(padding).toEqual(['36px', '24px', '46px', '24px']);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      const increase = page.getByRole('button', { name: 'PLAYER 1のライフを1増やす' });
      await increase.tap();
      await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('21');
      expect(
        await increase.evaluate((element) => getComputedStyle(element).transitionDuration),
      ).toBe('0s');
      const endTurn = page.getByRole('button', { name: 'ターン終了' });
      await endTurn.scrollIntoViewIfNeeded();
      const rect = await endTurn.boundingBox();
      expect(rect!.x).toBeGreaterThanOrEqual(24);
      expect(rect!.x + rect!.width).toBeLessThanOrEqual(width - 24);
      await endTurn.tap();
      await expect(page.getByLabel('現在のターン')).toHaveText('2');
    });
  });
}
