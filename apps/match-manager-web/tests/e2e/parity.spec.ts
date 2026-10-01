import { readFileSync } from 'node:fs';
import { test, expect } from '@playwright/test';
import type { CommandResult, MatchCommand } from '../../src/matchSession';

type Step = CommandResult & { command: MatchCommand };

test('actual browser Wasm matches Desktop SQLite after every command', async ({ page }) => {
  const steps = JSON.parse(
    readFileSync(new URL('../generated/desktop-parity.json', import.meta.url), 'utf8'),
  ) as Step[];
  await page.goto('/');
  const results = await page.evaluate(
    async (commands) => {
      const modulePath = '/src/matchSession.ts';
      const { createMatchSession } = await import(modulePath);
      let session = await createMatchSession('parity');
      const results = [];
      for (const [index, command] of commands.entries()) {
        results.push(await session.dispatch(command));
        if (index % 30 === 29) {
          session.close();
          session = await createMatchSession('parity');
        }
      }
      session.close();
      return results;
    },
    steps.map((step) => step.command),
  );
  expect(results).toHaveLength(steps.length);
  for (const [index, step] of steps.entries()) {
    expect(results[index], `command ${index}: ${JSON.stringify(step.command)}`).toEqual({
      changed: step.changed,
      state: step.state,
    });
  }
});

test('Wasm rejects malformed commands and unsafe revisions without advancing saved state', async ({
  page,
}) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const apiPath = '/src/wasmApi.ts';
    const sessionPath = '/src/matchSession.ts';
    const engine = await (await import(apiPath)).loadWasm();
    const session = await (await import(sessionPath)).createMatchSession('validation');
    const initial = session.state;
    let rejected = 0;
    for (const command of [
      { type: 'set_life', player: 'player_one', life: 1000 },
      { type: 'unknown' },
    ]) {
      try {
        await session.dispatch(command);
      } catch {
        rejected++;
      }
    }
    for (const [state, command] of [
      ['{}', '{"type":"end_turn"}'],
      [JSON.stringify({ ...initial, revision: Number.MAX_SAFE_INTEGER }), '{"type":"end_turn"}'],
      [JSON.stringify(initial), '{'],
    ]) {
      try {
        engine.apply_command(state, command);
      } catch {
        rejected++;
      }
    }
    const unchanged = JSON.stringify(initial) === JSON.stringify((await session.snapshot()).state);
    session.close();
    return { rejected, unchanged };
  });
  expect(result).toEqual({ rejected: 5, unchanged: true });
});
