import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('renders the environment setup confirmation', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: '環境構築が完了しました' })).toBeInTheDocument();
  });
});
