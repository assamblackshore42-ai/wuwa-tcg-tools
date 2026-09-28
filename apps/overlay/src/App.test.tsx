import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('manages both life counters independently', () => {
    render(<App />);

    const playerOneLife = screen.getByLabelText('PLAYER 1の現在ライフ');
    const playerTwoLife = screen.getByLabelText('PLAYER 2の現在ライフ');

    fireEvent.click(screen.getByRole('button', { name: 'PLAYER 1のライフを1減らす' }));

    expect(playerOneLife).toHaveTextContent('19');
    expect(playerTwoLife).toHaveTextContent('20');
  });

  it('resets a life counter to its initial value', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'PLAYER 2のライフを1増やす' }));
    fireEvent.click(screen.getByRole('button', { name: 'PLAYER 2のライフを20に戻す' }));

    expect(screen.getByLabelText('PLAYER 2の現在ライフ')).toHaveTextContent('20');
  });

  it('shows the selected battle status', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'P1 優勢' }));

    expect(screen.getByText('PLAYER 1が優勢')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'P1 優勢' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('tracks turn actions and clears them when the turn ends', () => {
    render(<App />);

    const levelUp = screen.getByRole('button', { name: 'レベルアップを使用済みにする' });
    fireEvent.click(levelUp);

    expect(screen.getByRole('button', { name: 'レベルアップを未使用に戻す' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    fireEvent.click(screen.getByRole('button', { name: 'ターン終了' }));

    expect(screen.getByLabelText('現在のターン')).toHaveTextContent('2');
    expect(screen.getByText('PLAYER 2', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'レベルアップを使用済みにする' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });
});
