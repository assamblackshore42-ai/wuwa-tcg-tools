import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MatchState } from './api/matchApi';
import { App } from './App';
import { useMatchStore } from './store/matchStore';

const INITIAL_MATCH: MatchState = {
  revision: 0,
  players: [
    { id: 'player_one', name: 'PLAYER 1', life: 20 },
    { id: 'player_two', name: 'PLAYER 2', life: 20 },
  ],
  battleStatus: 'even',
  turn: {
    number: 1,
    activePlayer: 'player_one',
    usedActions: [],
  },
};

describe('App', () => {
  const sendCommand = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    window.history.pushState({}, '', '/');
    sendCommand.mockClear();
    useMatchStore.setState({
      match: structuredClone(INITIAL_MATCH),
      connectionStatus: 'connected',
      error: null,
      connect: () => () => undefined,
      sendCommand,
    });
  });

  it('sends life operations as commands instead of mutating local state', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }));
    fireEvent.click(screen.getByRole('button', { name: 'PLAYER 2のライフを20に戻す' }));

    expect(sendCommand).toHaveBeenNthCalledWith(1, {
      type: 'adjust_life',
      player: 'player_one',
      amount: -1,
    });
    expect(sendCommand).toHaveBeenNthCalledWith(2, {
      type: 'reset_life',
      player: 'player_two',
    });
  });

  it('sends battle and turn operations using the API contract', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'P1 優勢' }));
    fireEvent.click(screen.getByRole('button', { name: 'レベルアップを使用済みにする' }));
    fireEvent.click(screen.getByRole('button', { name: 'ターン終了' }));

    expect(sendCommand).toHaveBeenNthCalledWith(1, {
      type: 'set_battle_status',
      status: 'player_one_advantage',
    });
    expect(sendCommand).toHaveBeenNthCalledWith(2, {
      type: 'toggle_turn_action',
      action: 'level_up',
    });
    expect(sendCommand).toHaveBeenNthCalledWith(3, { type: 'end_turn' });
  });

  it('sends undo as a server command', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '直前の操作を元に戻す' }));

    expect(sendCommand).toHaveBeenCalledWith({ type: 'undo' });
  });

  it('confirms before resetting the match', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '新しい対戦' }));
    expect(screen.getByRole('dialog', { name: '新しい対戦を開始しますか？' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(sendCommand).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '新しい対戦' }));
    fireEvent.click(screen.getByRole('button', { name: '初期状態へ戻す' }));
    expect(sendCommand).toHaveBeenCalledWith({ type: 'reset_match' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders newer state received from the server', () => {
    render(<App />);

    act(() => {
      useMatchStore.setState({
        match: {
          ...structuredClone(INITIAL_MATCH),
          revision: 3,
          players: [
            { id: 'player_one', name: 'PLAYER 1', life: 17 },
            { id: 'player_two', name: 'PLAYER 2', life: 20 },
          ],
          battleStatus: 'player_two_advantage',
          turn: {
            number: 2,
            activePlayer: 'player_two',
            usedActions: ['charge'],
          },
        },
      });
    });

    expect(screen.getByLabelText('PLAYER 1の現在ライフ')).toHaveTextContent('17');
    expect(screen.getByText('PLAYER 2が優勢')).toBeInTheDocument();
    expect(screen.getByLabelText('現在のターン')).toHaveTextContent('2');
    expect(screen.getByRole('button', { name: 'チャージを未使用に戻す' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('renders a read-only presentation at the overlay route', () => {
    window.history.pushState({}, '', '/overlay');

    render(<App />);

    expect(screen.getByLabelText('PLAYER 1の現在ライフ')).toHaveTextContent('20');
    expect(
      screen.queryByRole('button', { name: 'PLAYER 1のライフを1減らす' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'P1 優勢' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'ターン終了' })).not.toBeInTheDocument();
    expect(screen.getByText('戦況は互角')).toBeInTheDocument();
    expect(screen.getByLabelText('現在のターン')).toHaveTextContent('1');
  });
});
