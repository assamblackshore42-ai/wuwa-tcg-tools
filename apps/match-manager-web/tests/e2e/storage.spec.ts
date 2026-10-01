import { test, expect } from '@playwright/test';

test('restores full match and Undo after closing and reopening IndexedDB', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    let session = await createMatchSession('restore');
    await session.dispatch({ type: 'adjust_life', player: 'player_one', amount: -3 });
    await session.dispatch({ type: 'set_battle_status', status: 'player_one_advantage' });
    await session.dispatch({ type: 'toggle_turn_action', action: 'charge' });
    await session.dispatch({ type: 'end_turn' });
    const saved = session.state;
    session.close();
    session = await createMatchSession('restore');
    const restored = session.state;
    const undo = await session.dispatch({ type: 'undo' });
    session.close();
    return { saved, restored, undo: undo.state };
  });
  expect(result.restored).toEqual(result.saved);
  expect(result.undo).toMatchObject({
    revision: 5,
    battleStatus: 'player_one_advantage',
    players: [{ life: 17 }, { life: 20 }],
    turn: { number: 1, activePlayer: 'player_one', usedActions: ['charge'] },
  });
});

test('queues burst commands in order and continues after a rejected command', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    const session = await createMatchSession('burst');
    const promises = Array.from({ length: 100 }, () => session.dispatch({ type: 'end_turn' }));
    const failed = session.dispatch({ type: 'set_life', player: 'player_one', life: 1000 }).then(
      () => false,
      () => true,
    );
    const last = session.dispatch({ type: 'end_turn' });
    await Promise.all(promises);
    const rejected = await failed;
    await last;
    const state = (await session.snapshot()).state;
    const count = await session.database.history.count();
    session.close();
    return { rejected, state, count };
  });
  expect(result.rejected).toBe(true);
  expect(result.state).toMatchObject({ revision: 101, turn: { number: 102 } });
  expect(result.count).toBe(101);
});

test('aborts metadata failure after history insert, then retries and restores Undo', async ({
  page,
}) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    let session = await createMatchSession('rollback');
    await session.dispatch({ type: 'end_turn' });
    const before = session.state;
    const fail = () => {
      throw new DOMException('injected quota failure', 'QuotaExceededError');
    };
    session.database.records.hook('updating', fail);
    let failed = false;
    try {
      await session.dispatch({ type: 'end_turn' });
    } catch {
      failed = true;
    }
    const cached = session.state;
    const saved = (await session.snapshot()).state;
    const count = await session.database.history.count();
    session.database.records.hook('updating').unsubscribe(fail);
    session.close();
    session = await createMatchSession('rollback');
    const restored = session.state;
    const undo = await session.dispatch({ type: 'undo' });
    session.close();
    return { failed, before, cached, saved, count, restored, undo };
  });
  expect(result.failed).toBe(true);
  expect(result.cached).toEqual(result.before);
  expect(result.saved).toEqual(result.before);
  expect(result.restored).toEqual(result.before);
  expect(result.count).toBe(1);
  expect(result.undo.state).toMatchObject({ revision: 2, turn: { number: 1 } });
});

test('failed Undo keeps the removed history entry and can be retried', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    const session = await createMatchSession('undo-failure');
    await session.dispatch({ type: 'end_turn' });
    const before = session.state;
    const fail = () => {
      throw new Error('injected write failure');
    };
    session.database.records.hook('updating', fail);
    let failed = false;
    try {
      await session.dispatch({ type: 'undo' });
    } catch {
      failed = true;
    }
    const saved = (await session.snapshot()).state;
    const count = await session.database.history.count();
    session.database.records.hook('updating').unsubscribe(fail);
    const undo = await session.dispatch({ type: 'undo' });
    session.close();
    return { failed, before, saved, count, undo };
  });
  expect(result.failed).toBe(true);
  expect(result.saved).toEqual(result.before);
  expect(result.count).toBe(1);
  expect(result.undo.state).toMatchObject({ revision: 2, turn: { number: 1 } });
});

test('failed retention pruning rolls back reset, baseline and deleted history together', async ({
  page,
}) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    const session = await createMatchSession('prune-failure');
    for (let index = 0; index < 49; index++) {
      await session.dispatch({ type: 'end_turn' });
      await session.dispatch({ type: 'reset_match' });
    }
    await session.dispatch({ type: 'end_turn' });
    const before = await session.database.records.get('current');
    const beforeCount = await session.database.history.count();
    const fail = () => {
      throw new Error('injected pruning failure');
    };
    session.database.history.hook('deleting', fail);
    let failed = false;
    try {
      await session.dispatch({ type: 'reset_match' });
    } catch {
      failed = true;
    }
    const after = await session.database.records.get('current');
    const afterCount = await session.database.history.count();
    session.database.history.hook('deleting').unsubscribe(fail);
    const retry = await session.dispatch({ type: 'reset_match' });
    const retained = await session.database.history.count();
    session.close();
    return { failed, before, beforeCount, after, afterCount, retry, retained };
  });
  expect(result.failed).toBe(true);
  expect(result.after).toEqual(result.before);
  expect(result.afterCount).toBe(result.beforeCount);
  expect(result.retry.state).toMatchObject({ revision: 100, turn: { number: 1 } });
  expect(result.retained).toBe(98);
});

test('rejects corrupt or unknown-format saved data without overwriting it', async ({ page }) => {
  await page.goto('/');
  const results = await page.evaluate(async () => {
    const path = '/src/matchSession.ts';
    const { createMatchSession } = await import(path);
    const dbPath = '/src/matchDatabase.ts';
    const { MatchDatabase } = await import(dbPath);
    const results = [];
    for (const issue of ['state', 'version', 'history', 'missing']) {
      const name = `corrupt-${issue}`;
      const session = await createMatchSession(name);
      await session.dispatch({ type: 'end_turn' });
      const record = await session.database.records.get('current');
      if (issue === 'state') record.state.turn.number = 0;
      if (issue === 'version') record.formatVersion = 99;
      if (issue === 'missing') await session.database.records.delete('current');
      else await session.database.records.put(record);
      if (issue === 'history') {
        const entry = await session.database.history.orderBy(':id').last();
        entry.state.players[0].life = 1000;
        await session.database.history.put(entry);
      }
      const before = JSON.stringify({
        record: await session.database.records.get('current'),
        history: await session.database.history.toArray(),
      });
      session.close();
      let rejected = false;
      try {
        (await createMatchSession(name)).close();
      } catch {
        rejected = true;
      }
      const database = new MatchDatabase(name);
      const after = JSON.stringify({
        record: await database.records.get('current'),
        history: await database.history.toArray(),
      });
      database.close();
      results.push({ rejected, preserved: before === after });
    }
    return results;
  });
  expect(results).toEqual(Array.from({ length: 4 }, () => ({ rejected: true, preserved: true })));
});

test('two tabs share committed state and simultaneous commands never lose updates', async ({
  context,
}) => {
  const first = await context.newPage();
  const second = await context.newPage();
  await Promise.all([first.goto('/'), second.goto('/')]);
  for (const page of [first, second])
    await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('20');
  await Promise.all(
    [first, second].map((page) =>
      page.evaluate(async () => {
        const path = '/src/matchStore.ts';
        const { useMatchStore } = await import(path);
        await Promise.all(
          Array.from({ length: 20 }, () =>
            useMatchStore
              .getState()
              .dispatch({ type: 'adjust_life', player: 'player_one', amount: 1 }),
          ),
        );
      }),
    ),
  );
  for (const page of [first, second])
    await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('60');
  await first.getByRole('button', { name: 'Undo', exact: true }).click();
  for (const page of [first, second])
    await expect(page.getByLabel('PLAYER 1の現在ライフ')).toHaveText('59');
  await second.reload();
  await expect(second.getByLabel('PLAYER 1の現在ライフ')).toHaveText('59');
});

test('refuses a newer database schema without changing its data or version', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const sessionPath = '/src/matchSession.ts';
    const { createMatchSession } = await import(sessionPath);
    const dbPath = '/src/matchDatabase.ts';
    const { MatchDatabase } = await import(dbPath);
    const session = await createMatchSession('future-schema');
    await session.dispatch({ type: 'end_turn' });
    const before = session.state;
    session.close();
    const future = new MatchDatabase('future-schema');
    future.version(2).stores({ records: 'id', history: '++id,isReset' });
    await future.open();
    future.close();
    let rejected = false;
    try {
      (await createMatchSession('future-schema')).close();
    } catch {
      rejected = true;
    }
    const inspect = new MatchDatabase('future-schema');
    inspect.version(2).stores({ records: 'id', history: '++id,isReset' });
    const record = await inspect.records.get('current');
    const version = inspect.verno;
    inspect.close();
    return {
      rejected,
      unchanged: JSON.stringify(before) === JSON.stringify(record.state),
      version,
    };
  });
  expect(result).toEqual({ rejected: true, unchanged: true, version: 2 });
});
