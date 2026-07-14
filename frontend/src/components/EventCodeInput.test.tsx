import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EventCodeInput from './EventCodeInput';

describe('EventCodeInput', () => {
  it('submits a normalized six character code', () => {
    const onSubmit = vi.fn();
    render(<EventCodeInput onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Six character event code'), { target: { value: 'ab23cd' } });
    fireEvent.click(screen.getByRole('button', { name: /find my photos/i }));

    expect(onSubmit).toHaveBeenCalledWith('AB23CD');
  });
});
